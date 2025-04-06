"""File storage module"""

import os
import uuid
from fastapi import UploadFile, HTTPException
from typing import Optional, Tuple, List
import logging
from motor.motor_asyncio import AsyncIOMotorGridFSBucket
from core.database import db
from bson import ObjectId

logger = logging.getLogger(__name__)

# Configuration
ALLOWED_EXTENSIONS = {'.pdf', '.doc', '.docx', '.txt', '.rtf'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

def get_file_extension(filename: str) -> str:
    """Get file extension"""
    return os.path.splitext(filename)[1].lower()

def is_allowed_file(filename: str) -> bool:
    """Check if file extension is allowed"""
    return get_file_extension(filename) in ALLOWED_EXTENSIONS

async def save_uploaded_file(file: UploadFile) -> Tuple[str, str]:
    """
    Save uploaded file to GridFS
    Returns tuple (filename, file_id)
    """
    try:
        # Check file extension
        if not is_allowed_file(file.filename):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
            )
            
        # Check file size
        file_size = 0
        content = []
        async for chunk in file.read(1024):
            content.append(chunk)
            file_size += len(chunk)
            if file_size > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=400,
                    detail=f"File too large. Maximum size: {MAX_FILE_SIZE/1024/1024}MB"
                )
                
        file_content = b''.join(content)
        
        # Save to GridFS
        fs = AsyncIOMotorGridFSBucket(db)
        file_id = await fs.upload_from_stream(
            file.filename,
            file_content
        )
        
        return file.filename, str(file_id)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving file: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Error saving file"
        )

async def get_file(file_id: str) -> Tuple[bytes, str]:
    """
    Get file from GridFS
    Returns tuple (file_content, filename)
    """
    try:
        # Get file from GridFS
        fs = AsyncIOMotorGridFSBucket(db)
        
        # Check if file exists
        if not await fs.find_one({"_id": file_id}):
            raise HTTPException(
                status_code=404,
                detail="File not found"
            )
            
        # Read file content
        grid_out = await fs.open_download_stream(file_id)
        file_content = await grid_out.read()
        filename = grid_out.filename
        
        return file_content, filename
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting file: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Error getting file"
        )

async def save_file_content(content: bytes, filename: str, user_id: str) -> str:
    """
    Save file bytes to GridFS
    Returns file_id
    """
    if not is_allowed_file(filename):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # Check file size
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE/1024/1024}MB"
        )

    try:
        # Get GridFS bucket
        db = get_db()
        fs = AsyncIOMotorGridFSBucket(db)
        
        # Upload file to GridFS
        file_id = await fs.upload_from_stream(
            filename,
            content,
            metadata={
                "user_id": user_id,
                "content_type": f"application/{get_file_extension(filename)[1:]}",
                "original_filename": filename
            }
        )
        
        return str(file_id)
        
    except Exception as e:
        logger.error(f"Error saving file: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Error saving file"
        )

async def delete_file(file_id: str) -> None:
    """
    Delete file from GridFS
    
    Args:
        file_id: GridFS file ID
    """
    try:
        db = get_db()
        fs = AsyncIOMotorGridFSBucket(db)
        await fs.delete(file_id)
    except Exception as e:
        logger.error(f"Error deleting file from GridFS: {str(e)}")
        raise 