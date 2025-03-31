from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorDatabase
from models import User, UserCreate, UserLogin, Token
from auth import (
    get_password_hash, verify_password, create_access_token,
    create_refresh_token, authenticate_user, get_current_user,
    init_db, db, refresh_access_token, ACCESS_TOKEN_EXPIRE_MINUTES
)
import logging
from dotenv import load_dotenv
import os
from datetime import timedelta

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

@app.get("/")
async def root():
    return {"message": "Welcome to Joba API"}

@app.get("/health")
async def health_check():
    try:
        # Проверяем подключение к базе данных
        if not db:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connection not initialized"
            )
        await db.command("ping")
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed"
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
        refresh_token = create_refresh_token(data={"sub": str(user.id)})
        return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}
    except Exception as e:
        logger.error(f"Error during signin: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@app.post("/refresh", response_model=Token)
async def refresh_token(refresh_token: str):
    """
    Обновление access token с помощью refresh token
    """
    try:
        access_token = await refresh_access_token(refresh_token)
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }
    except Exception as e:
        logger.error(f"Error during token refresh: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

@app.get("/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """
    Получение информации о текущем пользователе
    """
    return current_user

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