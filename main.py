from fastapi import FastAPI, HTTPException, Depends, status
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import os
import logging
from datetime import timedelta, datetime
from fastapi.security import OAuth2PasswordRequestForm
from models import UserCreate, Token, User, UserInDB
from auth import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    get_password_hash,
    authenticate_user,
    get_current_user
)
from bson import ObjectId

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()

app = FastAPI(title="FastAPI MongoDB Auth App")

# Подключение к MongoDB
MONGODB_URL = os.getenv("MONGODB_URL")
if not MONGODB_URL:
    raise ValueError("MONGODB_URL не установлен в переменных окружения")

# Создаем клиента MongoDB
client = AsyncIOMotorClient(MONGODB_URL)
db = client.jobadb

async def get_database():
    return db

@app.post("/signup", response_model=User)
async def create_user(user: UserCreate, db = Depends(get_database)):
    # Проверяем, существует ли пользователь
    if await db.users.find_one({"email": user.email}):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пользователь с таким email уже существует"
        )
    
    # Создаем пользователя в БД
    user_dict = user.dict()
    user_dict["hashed_password"] = get_password_hash(user_dict.pop("password"))
    user_dict["created_at"] = datetime.utcnow()
    user_dict["is_active"] = True
    
    result = await db.users.insert_one(user_dict)
    
    # Получаем созданного пользователя
    created_user = await db.users.find_one({"_id": result.inserted_id})
    return User(
        id=str(created_user["_id"]),
        email=created_user["email"],
        username=created_user["username"],
        created_at=created_user["created_at"],
        is_active=created_user["is_active"]
    )

@app.post("/signin", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db = Depends(get_database)):
    user = await authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/users/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user

@app.get("/health")
async def health_check(db = Depends(get_database)):
    try:
        await db.command("ping")
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        logger.error(f"Ошибка проверки здоровья базы данных: {str(e)}")
        raise HTTPException(status_code=503, detail="База данных недоступна") 