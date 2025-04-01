from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging

# Настройка логирования
logger = logging.getLogger(__name__)

# Глобальные переменные для клиента и базы данных
client = None
db = None

def get_db():
    """Получение экземпляра базы данных"""
    if db is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return db

async def init_db():
    """Инициализация подключения к базе данных"""
    global client, db
    
    try:
        # Получаем URL базы данных
        mongo_url = os.getenv("MONGO_URL")
        if not mongo_url:
            raise ValueError("MONGO_URL environment variable is not set")
        
        logger.info(f"Attempting to connect to MongoDB with URL: {mongo_url}")
        
        # Создаем клиент и подключаемся к базе данных
        client = AsyncIOMotorClient(mongo_url)
        await client.admin.command('ping')
        logger.info("Successfully pinged MongoDB server")
        
        # Инициализируем базу данных
        db = client.joba
        logger.info("Successfully initialized database connection")
        
        # Проверяем доступ к коллекции users
        await db.users.find_one()
        logger.info("Successfully accessed users collection")
    except Exception as e:
        logger.error(f"Failed to initialize database: {str(e)}")
        raise 