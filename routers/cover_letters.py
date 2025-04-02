from fastapi import APIRouter, Depends, HTTPException, status, Header
from typing import List, Optional
from models.cover_letters import CoverLetter, CoverLetterCreate
from core.auth import get_current_user
from models.users import User
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import os
from typing import Dict, Any
from fastapi.security import HTTPBearer
from core.database import get_db
from datetime import datetime

router = APIRouter(prefix="/cover-letters", tags=["cover-letters"])

security = HTTPBearer()

async def get_current_user_from_token(credentials: HTTPBearer = Depends(security)) -> User:
    return await get_current_user(credentials.credentials)

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
    total = await db.cover_letters.count_documents({"userId": user_id})
    
    # Получаем документы с пагинацией
    cursor = db.cover_letters.find({"userId": user_id}).skip(skip).limit(per_page)
    cover_letters = await cursor.to_list(length=per_page)
    
    # Преобразуем ObjectId в строки
    for letter in cover_letters:
        letter["_id"] = str(letter["_id"])
    
    return {
        "list": cover_letters,
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
    current_user: User = Depends(get_current_user_from_token)
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

@router.post("/create", response_model=CoverLetter)
async def create_cover_letter(
    cover_letter: CoverLetterCreate,
    current_user: User = Depends(get_current_user_from_token)
):
    """
    Создание нового cover letter
    """
    try:
        db = get_db()
        
        # Создаем документ
        cover_letter_dict = cover_letter.dict()
        cover_letter_dict["userId"] = str(current_user.id)
        cover_letter_dict["createdAt"] = datetime.utcnow()
        cover_letter_dict["updatedAt"] = datetime.utcnow()
        
        # Вставляем документ в базу данных
        result = await db.cover_letters.insert_one(cover_letter_dict)
        
        # Получаем созданный документ
        created_letter = await db.cover_letters.find_one({"_id": result.inserted_id})
        created_letter["_id"] = str(created_letter["_id"])
        
        return CoverLetter(**created_letter)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/{cover_letter_id}", response_model=CoverLetter)
async def get_cover_letter(
    cover_letter_id: str,
    current_user: User = Depends(get_current_user_from_token)
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
            "userId": str(current_user.id)
        })
        
        if not cover_letter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cover letter not found or access denied"
            )
        
        # Преобразуем ObjectId в строку
        cover_letter["_id"] = str(cover_letter["_id"])
        
        return CoverLetter(**cover_letter)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        ) 