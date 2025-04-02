import os
import uuid
from fastapi import UploadFile, HTTPException
from typing import Optional, Tuple
import logging
from motor.motor_asyncio import AsyncIOMotorGridFSBucket
from core.database import get_db
from bson import ObjectId

logger = logging.getLogger(__name__)

# Конфигурация
ALLOWED_EXTENSIONS = {'.pdf', '.doc', '.docx'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

def get_file_extension(filename: str) -> str:
    """Получение расширения файла"""
    return os.path.splitext(filename)[1].lower()

def is_allowed_file(filename: str) -> bool:
    """Проверка разрешенного расширения файла"""
    return get_file_extension(filename) in ALLOWED_EXTENSIONS

async def save_upload_file(upload_file: UploadFile, user_id: str) -> Tuple[str, str]:
    """
    Сохранение загруженного файла в GridFS
    Возвращает tuple (filename, file_id)
    """
    if not is_allowed_file(upload_file.filename):
        raise HTTPException(
            status_code=400,
            detail=f"Недопустимый тип файла. Разрешены: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # Проверка размера файла
    file_size = 0
    chunk_size = 1024 * 1024  # 1MB
    while chunk := await upload_file.read(chunk_size):
        file_size += len(chunk)
        if file_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"Файл слишком большой. Максимальный размер: {MAX_FILE_SIZE/1024/1024}MB"
            )
    await upload_file.seek(0)

    try:
        # Получаем GridFS bucket
        db = get_db()
        fs = AsyncIOMotorGridFSBucket(db)
        
        # Загружаем файл в GridFS
        file_id = await fs.upload_from_stream(
            upload_file.filename,
            upload_file.file,
            metadata={
                "user_id": user_id,
                "content_type": upload_file.content_type,
                "original_filename": upload_file.filename
            }
        )
        
        return upload_file.filename, str(file_id)
        
    except Exception as e:
        logger.error(f"Ошибка при сохранении файла: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Ошибка при сохранении файла"
        )

async def get_file(file_id: str) -> Tuple[bytes, str]:
    """
    Получение файла из GridFS
    Возвращает tuple (file_content, filename)
    """
    try:
        db = get_db()
        fs = AsyncIOMotorGridFSBucket(db)
        
        # Получаем файл из GridFS
        grid_out = await fs.open_download_stream(ObjectId(file_id))
        if not grid_out:
            raise HTTPException(
                status_code=404,
                detail="Файл не найден"
            )
            
        # Читаем содержимое файла
        file_content = await grid_out.read()
        filename = grid_out.filename
        
        return file_content, filename
        
    except Exception as e:
        logger.error(f"Ошибка при получении файла: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Ошибка при получении файла"
        ) 