from motor.motor_asyncio import AsyncIOMotorClient
from core.config import get_settings
import logging

# Настройка логирования
logger = logging.getLogger(__name__)

# Глобальные переменные для клиента и базы данных
client = None
db = None

settings = get_settings()

async def init_db():
    """Initialize database connection"""
    global client, db
    
    try:
        client = AsyncIOMotorClient(settings.MONGO_URL)
        await client.admin.command('ping')
        db = client[settings.DATABASE_NAME]
        logger.info("Successfully connected to MongoDB")
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {str(e)}")
        raise

def get_db():
    """Get database instance"""
    if db is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return db 