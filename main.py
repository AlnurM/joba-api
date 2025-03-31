from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from models import User, UserCreate, UserLogin, Token
from auth import (
    authenticate_user, create_user, get_current_user,
    create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES, db, init_db
)
from datetime import timedelta
import os
from dotenv import load_dotenv
import logging
from contextlib import asynccontextmanager

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    try:
        await init_db()
        logger.info("Successfully connected to MongoDB")
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Closing MongoDB connection")

app = FastAPI(title="Joba API", lifespan=lifespan)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/signup", response_model=User)
async def signup(user: UserCreate):
    """
    Регистрация нового пользователя.
    Требуется только email и пароль, username опционален.
    """
    try:
        return await create_user(user)
    except Exception as e:
        logger.error(f"Error during signup: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@app.post("/signin", response_model=Token)
async def signin(user_data: UserLogin):
    """
    Вход в систему.
    Можно использовать email или username для входа.
    """
    try:
        logger.info(f"Attempting to authenticate user with login: {user_data.login}")
        user = await authenticate_user(user_data.login, user_data.password)
        if not user:
            logger.warning(f"Authentication failed for login: {user_data.login}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect login or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        logger.info(f"User authenticated successfully: {user.email}")
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": str(user.id)}, expires_delta=access_token_expires
        )
        return {"access_token": access_token, "token_type": "bearer"}
    except Exception as e:
        logger.error(f"Error during signin: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@app.get("/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """
    Получение информации о текущем пользователе
    """
    return current_user

@app.get("/health")
async def health_check():
    """
    Проверка здоровья API и подключения к базе данных
    """
    try:
        await db.command("ping")
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed"
        )

@app.get("/debug/users")
async def debug_users():
    """
    Отладочный эндпоинт для просмотра всех пользователей
    """
    try:
        users = await db.users.find().to_list(length=100)
        return [{"id": str(user["_id"]), "email": user["email"], "username": user.get("username")} for user in users]
    except Exception as e:
        logger.error(f"Error getting users: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        ) 