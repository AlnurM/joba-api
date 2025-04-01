from fastapi import APIRouter, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorClient
import logging
import os

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/")
async def root():
    return {"message": "Welcome to Joba API"}

@router.get("/health")
async def health_check():
    try:
        # Получаем URL базы данных
        mongodb_url = os.getenv("MONGO_URL")
        if not mongodb_url:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="MongoDB URL not configured"
            )
        
        # Создаем временное подключение для проверки
        client = AsyncIOMotorClient(
            mongodb_url,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000
        )
        
        # Проверяем подключение через ping
        await client.admin.command('ping')
        
        # Проверяем доступ к базе данных и коллекции
        test_db = client.joba
        await test_db.users.find_one()
        
        return {
            "status": "healthy",
            "database": {
                "connected": True,
                "ping": "success",
                "users_collection": "accessible"
            }
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e)
        ) 