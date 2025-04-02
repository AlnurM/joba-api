from fastapi import UploadFile, HTTPException
from typing import Tuple
import os
from motor.motor_asyncio import AsyncIOMotorGridFSBucket
from core.database import get_db
from core.config import get_settings
from core.exceptions import StorageError, ValidationError
from bson import ObjectId

settings = get_settings()

def get_file_extension(filename: str) -> str:
    return os.path.splitext(filename)[1].lower()

def is_allowed_file(filename: str) -> bool:
    return get_file_extension(filename) in settings.ALLOWED_EXTENSIONS

class StorageService:
    def __init__(self):
        self.fs = AsyncIOMotorGridFSBucket(get_db())
        self.max_file_size = settings.MAX_FILE_SIZE

    async def save(self, file: UploadFile, user_id: str) -> Tuple[str, str]:
        """Save file to GridFS and return (filename, file_id)"""
        if not is_allowed_file(file.filename):
            raise ValidationError(f"Invalid file type. Allowed: {', '.join(settings.ALLOWED_EXTENSIONS)}")

        # Check file size
        file_size = 0
        chunk_size = 1024 * 1024  # 1MB
        while chunk := await file.read(chunk_size):
            file_size += len(chunk)
            if file_size > self.max_file_size:
                raise ValidationError(f"File too large. Max size: {self.max_file_size/1024/1024}MB")
        await file.seek(0)

        try:
            file_id = await self.fs.upload_from_stream(
                file.filename,
                file.file,
                metadata={
                    "user_id": user_id,
                    "content_type": file.content_type,
                    "original_filename": file.filename
                }
            )
            return file.filename, str(file_id)
        except Exception as e:
            raise StorageError(f"Failed to save file: {str(e)}")

    async def get(self, file_id: str) -> Tuple[bytes, str]:
        """Get file from GridFS and return (content, filename)"""
        try:
            grid_out = await self.fs.open_download_stream(ObjectId(file_id))
            if not grid_out:
                raise StorageError("File not found")
            
            file_content = await grid_out.read()
            return file_content, grid_out.filename
        except Exception as e:
            raise StorageError(f"Failed to get file: {str(e)}") 