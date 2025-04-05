from fastapi import APIRouter, Depends, HTTPException, status, Header
from typing import List, Optional
from models.cover_letters import CoverLetter, CoverLetterCreate, CoverLetterStatus, CoverLetterStatusUpdate
from core.auth import get_current_user
from models.users import User
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import os
from typing import Dict, Any
from core.database import get_db
from datetime import datetime

router = APIRouter(prefix="/cover-letters", tags=["cover-letters"])

async def get_cover_letters_by_user(
    user_id: str,
    page: int = 1,
    per_page: int = 10
) -> Dict[str, Any]:
    """
    Получение cover letters пользователя с пагинацией
    """
    skip = (page - 1) * per_page
    db = get_db()
    
    # Получаем общее количество документов
    total = await db.cover_letters.count_documents({"user_id": user_id})
    
    # Получаем документы с пагинацией
    cursor = db.cover_letters.find({"user_id": user_id}).sort("created_at", -1).skip(skip).limit(per_page)
    cover_letters = await cursor.to_list(length=per_page)
    
    # Преобразуем ObjectId в строки
    processed_letters = []
    for letter in cover_letters:
        letter_dict = {
            "id": str(letter["_id"]),
            "user_id": letter["user_id"],
            "name": letter["name"],
            "content": letter["content"],
            "status": letter.get("status", CoverLetterStatus.ARCHIVED),
            "created_at": letter.get("created_at", datetime.utcnow()),
            "updated_at": letter.get("updated_at", datetime.utcnow())
        }
        processed_letters.append(letter_dict)
    
    return {
        "list": processed_letters,
        "pagination": {
            "total": total,
            "currentPage": page,
            "totalPages": (total + per_page - 1) // per_page,
            "perPage": per_page
        }
    }

@router.get("/list", response_model=Dict[str, Any])
async def list_cover_letters(
    page: int = 1,
    per_page: int = 10,
    current_user: User = Depends(get_current_user)
):
    """
    Получение списка cover letters текущего пользователя с пагинацией
    """
    try:
        return await get_cover_letters_by_user(
            user_id=str(current_user.id),
            page=page,
            per_page=per_page
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("", response_model=CoverLetter)
async def create_cover_letter(
    cover_letter: CoverLetterCreate,
    current_user: User = Depends(get_current_user)
):
    """
    Создание нового cover letter
    """
    try:
        db = get_db()
        
        # Добавляем системные поля
        cover_letter_dict = cover_letter.model_dump()
        cover_letter_dict.update({
            "user_id": str(current_user.id),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        })
        
        # Сохраняем в базу данных
        result = await db.cover_letters.insert_one(cover_letter_dict)
        
        # Получаем созданный документ
        created_letter = await db.cover_letters.find_one({"_id": result.inserted_id})
        created_letter["id"] = str(created_letter.pop("_id"))
        
        return CoverLetter(**created_letter)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/{cover_letter_id}", response_model=CoverLetter)
async def get_cover_letter(
    cover_letter_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Получение cover letter по ID.
    Проверяет, что документ принадлежит текущему пользователю.
    """
    try:
        db = get_db()
        
        # Проверяем валидность ObjectId
        try:
            object_id = ObjectId(cover_letter_id)
        except:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid cover letter ID format"
            )
        
        # Ищем документ с проверкой принадлежности пользователю
        cover_letter = await db.cover_letters.find_one({
            "_id": object_id,
            "user_id": str(current_user.id)
        })
        
        if not cover_letter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cover letter not found or access denied"
            )
        
        # Преобразуем ObjectId в строку
        cover_letter["id"] = str(cover_letter.pop("_id"))
        
        return CoverLetter(**cover_letter)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.patch("/{cover_letter_id}/status", response_model=CoverLetter)
async def update_cover_letter_status(
    cover_letter_id: str,
    status_update: CoverLetterStatusUpdate,
    current_user: User = Depends(get_current_user)
):
    """
    Обновление статуса cover letter
    """
    try:
        db = get_db()
        
        # Проверяем валидность ObjectId
        try:
            object_id = ObjectId(cover_letter_id)
        except:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid cover letter ID format"
            )
        
        # Проверяем существование документа и права доступа
        cover_letter = await db.cover_letters.find_one({
            "_id": object_id,
            "user_id": str(current_user.id)
        })
        
        if not cover_letter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cover letter not found or access denied"
            )
        
        # Обновляем статус
        result = await db.cover_letters.update_one(
            {"_id": object_id},
            {
                "$set": {
                    "status": status_update.status,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        if result.modified_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cover letter not updated"
            )
        
        # Получаем обновленный документ
        updated_letter = await db.cover_letters.find_one({"_id": object_id})
        updated_letter["id"] = str(updated_letter.pop("_id"))
        
        return CoverLetter(**updated_letter)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.delete("/{cover_letter_id}", status_code=status.HTTP_200_OK)
async def delete_cover_letter(
    cover_letter_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Удаление cover letter
    """
    try:
        db = get_db()
        
        # Проверяем валидность ObjectId
        try:
            object_id = ObjectId(cover_letter_id)
        except:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid cover letter ID format"
            )
        
        # Проверяем существование документа и права доступа
        cover_letter = await db.cover_letters.find_one({
            "_id": object_id,
            "user_id": str(current_user.id)
        })
        
        if not cover_letter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cover letter not found or access denied"
            )
        
        # Удаляем документ
        result = await db.cover_letters.delete_one({"_id": object_id})
        
        if result.deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cover letter not deleted"
            )
        
        return {"message": "Cover letter successfully deleted", "id": cover_letter_id}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        ) 