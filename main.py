from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorDatabase
from core.database import init_db
import logging
from dotenv import load_dotenv
import os
from routers import auth, default

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()

# Получение порта из переменных окружения (для Railway)
PORT = int(os.getenv("PORT", "8080"))

app = FastAPI(
    title="Joba API",
    description="API для сервиса Joba",
    version="1.0.0"
)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    try:
        await init_db()
        logger.info("Successfully connected to MongoDB")
        logger.info(f"Application will run on port: {PORT}")
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {str(e)}")
        raise

# Подключаем роутеры
app.include_router(default.router)
app.include_router(auth.router) 