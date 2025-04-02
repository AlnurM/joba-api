from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status, Response
from models import Resume, ResumeCreate, User
from models.resumes import ResumeStatus
from core.auth import get_current_user
from core.storage import save_upload_file, get_file
from core.database import get_db
from datetime import datetime
import logging
from typing import List, Dict, Any
from bson import ObjectId
from fastapi.security import HTTPBearer

router = APIRouter(prefix="/resumes", tags=["resumes"])
logger = logging.getLogger(__name__)

security = HTTPBearer()

async def get_current_user_from_token(credentials: HTTPBearer = Depends(security)) -> User:
    return await get_current_user(credentials.credentials)

async def get_resumes_by_user(
    user_id: str,
    page: int = 1,
    per_page: int = 10
) -> Dict[str, Any]:
    """
    Получение резюме пользователя с пагинацией
    """
    skip = (page - 1) * per_page
    db = get_db()
    
    # Получаем общее количество документов
    total = await db.resumes.count_documents({"user_id": user_id})
    
    # Получаем документы с пагинацией
    cursor = db.resumes.find({"user_id": user_id}).skip(skip).limit(per_page)
    resumes = await cursor.to_list(length=per_page)
    
    # Преобразуем ObjectId в строки и создаем словари для каждого резюме
    processed_resumes = []
    for resume in resumes:
        resume_dict = {
            "id": str(resume["_id"]),
            "user_id": resume["user_id"],
            "filename": resume["filename"],
            "file_id": resume["file_id"],
            "status": resume["status"],
            "created_at": resume["created_at"]
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
    current_user: User = Depends(get_current_user_from_token)
):
    """
    Загрузка нового резюме
    """
    try:
        # Сохранение файла в GridFS
        filename, file_id = await save_upload_file(file, str(current_user.id))
        
        # Создание записи в базе данных
        db = get_db()
        resume_data = {
            "user_id": str(current_user.id),
            "filename": filename,
            "file_id": file_id,
            "status": ResumeStatus.ACTIVE,
            "created_at": datetime.utcnow()
        }
        
        result = await db.resumes.insert_one(resume_data)
        resume_data["id"] = str(result.inserted_id)
        
        return Resume(**resume_data)
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Ошибка при загрузке резюме: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при загрузке резюме"
        )

@router.get("/list", response_model=Dict[str, Any])
async def list_resumes(
    page: int = 1,
    per_page: int = 10,
    current_user: User = Depends(get_current_user_from_token)
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
    current_user: User = Depends(get_current_user_from_token)
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
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Ошибка при скачивании резюме: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при скачивании резюме"
        ) 