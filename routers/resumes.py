from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status, Response, Form
from models import Resume, ResumeCreate, User, ResumeStatusUpdate
from models.resumes import ResumeStatus
from core.auth import get_current_user
from core.storage import save_file_content, get_file, is_allowed_file, ALLOWED_EXTENSIONS
from core.database import get_db
from core.resume_processor import process_resume
from datetime import datetime
import logging
from typing import List, Dict, Any
from bson import ObjectId
import os
import json
from motor.motor_asyncio import AsyncIOMotorGridFSBucket

router = APIRouter(prefix="/resumes", tags=["resumes"])
logger = logging.getLogger(__name__)

async def get_resumes_by_user(
    user_id: str,
    page: int = 1,
    per_page: int = 10
) -> Dict[str, Any]:
    """
    Получение резюме пользователя с пагинацией.
    Сортировка по дате создания - от недавнего к старому.
    """
    skip = (page - 1) * per_page
    db = get_db()
    
    # Получаем общее количество документов
    total = await db.resumes.count_documents({"user_id": user_id})
    
    # Получаем документы с пагинацией и сортировкой по дате создания (от новых к старым)
    cursor = db.resumes.find({"user_id": user_id}).sort("created_at", -1).skip(skip).limit(per_page)
    resumes = await cursor.to_list(length=per_page)
    
    # Преобразуем ObjectId в строки и создаем словари для каждого резюме
    processed_resumes = []
    for resume in resumes:
        resume_dict = {
            "id": str(resume["_id"]),
            "user_id": resume["user_id"],
            "filename": resume["filename"],
            "file_id": resume.get("file_id", ""),
            "status": resume.get("status", ResumeStatus.ARCHIVED),
            "created_at": resume.get("created_at", datetime.utcnow())
        }
        processed_resumes.append(resume_dict)
    
    return {
        "list": processed_resumes,
        "pagination": {
            "total": total,
            "currentPage": page,
            "totalPages": (total + per_page - 1) // per_page,
            "perPage": per_page
        }
    }

@router.post("/upload", response_model=Resume)
async def upload_resume(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Загружает резюме и сохраняет его в базу данных.
    
    Args:
        file: Файл резюме
        current_user: Текущий пользователь
        db: Подключение к базе данных
        
    Returns:
        Resume с информацией о загруженном резюме
    """
    try:
        # Проверяем расширение файла
        file_extension = os.path.splitext(file.filename)[1].lower()
        if file_extension not in ['.pdf', '.doc', '.docx']:
            raise HTTPException(
                status_code=400,
                detail="Неподдерживаемый формат файла. Поддерживаются только PDF, DOC и DOCX"
            )
            
        # Читаем содержимое файла
        file_content = await file.read()
        
        # Сохраняем файл в GridFS
        file_id = await save_file_content(file_content, file.filename, str(current_user.id))
        
        # Обрабатываем резюме
        logger.info(f"Начинаем обработку резюме {file.filename}")
        processed_data = await process_resume(file_content, file_extension)
        
        # Добавляем системные поля
        resume_data = {
            **processed_data,
            "user_id": str(current_user.id),
            "filename": file.filename,
            "file_id": file_id,
            "status": ResumeStatus.ARCHIVED,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        # Сохраняем в базу данных
        result = await db.resumes.insert_one(resume_data)
        resume_data["id"] = str(result.inserted_id)
        
        logger.info(f"Резюме успешно сохранено в базу данных, ID: {resume_data['id']}")
        
        return Resume(**resume_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при загрузке резюме: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при загрузке резюме: {str(e)}"
        )

@router.get("/list", response_model=Dict[str, Any])
async def list_resumes(
    page: int = 1,
    per_page: int = 10,
    current_user: User = Depends(get_current_user)
):
    """
    Получение списка резюме текущего пользователя с пагинацией
    """
    try:
        return await get_resumes_by_user(
            user_id=str(current_user.id),
            page=page,
            per_page=per_page
        )
    except Exception as e:
        logger.error(f"Ошибка при получении списка резюме: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при получении списка резюме"
        )

@router.get("/{resume_id}/download")
async def download_resume(
    resume_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Скачивание резюме
    """
    try:
        # Получаем информацию о резюме
        db = get_db()
        resume = await db.resumes.find_one({
            "_id": ObjectId(resume_id),
            "user_id": str(current_user.id)
        })
        
        if not resume:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Резюме не найдено"
            )
        
        # Получаем файл из GridFS
        file_content, filename = await get_file(resume["file_id"])
        
        # Возвращаем файл
        return Response(
            content=file_content,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при скачивании резюме: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при скачивании резюме"
        )

@router.post("/test-process")
async def test_process_resume(
    file: UploadFile = File(...),
):
    """
    Тестовый эндпоинт для анализа резюме без сохранения
    """
    try:
        # Проверяем тип файла
        if not is_allowed_file(file.filename):
            raise HTTPException(
                status_code=400,
                detail=f"Недопустимый тип файла. Разрешены: {', '.join(ALLOWED_EXTENSIONS)}"
            )

        # Получаем расширение файла
        file_extension = os.path.splitext(file.filename)[1]
        
        # Читаем содержимое файла
        content = await file.read()
        
        try:
            # Анализируем резюме
            result = await process_resume(content, file_extension)
            return result
            
        except Exception as e:
            logger.error(f"Ошибка при анализе резюме: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Не удалось проанализировать резюме"
            )
            
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Ошибка при обработке файла: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Ошибка при обработке файла"
        )

@router.delete("/{resume_id}", status_code=status.HTTP_200_OK)
async def delete_resume(
    resume_id: str,
    current_user: User = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Удаляет резюме по ID
    
    Args:
        resume_id: ID резюме для удаления
        current_user: Текущий пользователь
        db: Подключение к базе данных
        
    Returns:
        Статус 200 OK при успешном удалении
    """
    try:
        # Проверяем валидность ObjectId
        try:
            object_id = ObjectId(resume_id)
        except:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Некорректный формат ID резюме"
            )
        
        # Проверяем, что резюме существует и принадлежит текущему пользователю
        resume = await db.resumes.find_one({
            "_id": object_id,
            "user_id": str(current_user.id)
        })
        
        if not resume:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Резюме не найдено или доступ запрещен"
            )
        
        # Если у нас есть файл, также удаляем его из GridFS
        if "file_id" in resume:
            fs = AsyncIOMotorGridFSBucket(db)
            try:
                await fs.delete(ObjectId(resume["file_id"]))
                logger.info(f"Файл резюме удален из GridFS: {resume['file_id']}")
            except Exception as e:
                logger.warning(f"Не удалось удалить файл резюме из GridFS: {str(e)}")
        
        # Удаляем резюме из базы данных
        result = await db.resumes.delete_one({"_id": object_id})
        
        if result.deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Резюме не удалено"
            )
        
        logger.info(f"Резюме успешно удалено: {resume_id}")
        return {"message": "Резюме успешно удалено", "id": resume_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при удалении резюме: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при удалении резюме: {str(e)}"
        )

@router.patch("/{resume_id}/status", status_code=status.HTTP_200_OK)
async def update_resume_status(
    resume_id: str,
    status_update: ResumeStatusUpdate,
    current_user: User = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Изменяет статус резюме
    
    Args:
        resume_id: ID резюме
        status_update: Новый статус
        current_user: Текущий пользователь
        db: Подключение к базе данных
        
    Returns:
        Обновленное резюме
    """
    try:
        # Проверяем валидность ObjectId
        try:
            object_id = ObjectId(resume_id)
        except:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Некорректный формат ID резюме"
            )
        
        # Проверяем, что резюме существует и принадлежит текущему пользователю
        resume = await db.resumes.find_one({
            "_id": object_id,
            "user_id": str(current_user.id)
        })
        
        if not resume:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Резюме не найдено или доступ запрещен"
            )
        
        # Обновляем статус
        result = await db.resumes.update_one(
            {"_id": object_id},
            {"$set": {"status": status_update.status}}
        )
        
        if result.modified_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Резюме не обновлено"
            )
        
        # Получаем обновленное резюме
        updated_resume = await db.resumes.find_one({"_id": object_id})
        updated_resume["id"] = str(updated_resume["_id"])
        
        logger.info(f"Статус резюме успешно обновлен: {resume_id}")
        return Resume(**updated_resume)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при обновлении статуса резюме: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при обновлении статуса резюме: {str(e)}"
        ) 