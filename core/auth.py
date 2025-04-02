from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
import os
import logging
from domain.models import User, UserCreate, Token
from core.database import get_db
from bson.objectid import ObjectId
from core.config import settings

# Настройка логирования
logger = logging.getLogger(__name__)

# Настройка хеширования паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=settings.ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

async def create_user(user: UserCreate) -> User:
    """Создание нового пользователя"""
    db = get_db()
    
    # Проверяем, существует ли пользователь с таким email
    if await db.users.find_one({"email": user.email}):
        raise ValueError("Email already registered")
    
    # Проверяем, существует ли пользователь с таким username (если указан)
    if user.username and await db.users.find_one({"username": user.username}):
        raise ValueError("Username already taken")
    
    # Создаем нового пользователя
    hashed_password = get_password_hash(user.password)
    user_dict = user.dict()
    user_dict["password"] = hashed_password
    user_dict["created_at"] = datetime.utcnow()
    
    result = await db.users.insert_one(user_dict)
    user_dict["id"] = str(result.inserted_id)
    return User(**user_dict)

async def authenticate_user(login: str, password: str) -> Optional[User]:
    """Аутентификация пользователя по email или username"""
    db = get_db()
    
    # Ищем пользователя по email или username
    user = await db.users.find_one({
        "$or": [
            {"email": login},
            {"username": login}
        ]
    })
    
    if not user:
        return None
    
    if not verify_password(password, user["password"]):
        return None
    
    user["id"] = str(user["_id"])
    return User(**user)

async def get_current_user(token: str) -> User:
    """Получение текущего пользователя по токену"""
    credentials_exception = ValueError("Could not validate credentials")
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    db = get_db()
    try:
        # Преобразуем строковый ID в ObjectId
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if user is None:
            raise credentials_exception
        
        # Преобразуем ObjectId в строку для id
        user["id"] = str(user["_id"])
        # Удаляем _id, так как он не нужен в модели
        del user["_id"]
        return User(**user)
    except Exception as e:
        logger.error(f"Error getting user: {str(e)}")
        raise credentials_exception

async def refresh_access_token(refresh_token: str) -> str:
    """Обновление access token с помощью refresh token"""
    try:
        payload = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise ValueError("Invalid refresh token")
        
        db = get_db()
        # Проверяем, существует ли пользователь
        user = await db.users.find_one({"_id": user_id})
        if user is None:
            raise ValueError("User not found")
        
        # Создаем новый access token
        access_token_expires = timedelta(hours=settings.ACCESS_TOKEN_EXPIRE_HOURS)
        access_token = create_access_token(
            data={"sub": str(user_id)}, expires_delta=access_token_expires
        )
        return access_token
    except JWTError:
        raise ValueError("Invalid refresh token")

async def check_availability(email: Optional[str] = None, username: Optional[str] = None) -> tuple[bool, str]:
    """Проверка доступности email и username"""
    db = get_db()
    
    if email and await db.users.find_one({"email": email}):
        return False, "Email already registered"
    
    if username and await db.users.find_one({"username": username}):
        return False, "Username already taken"
    
    return True, "Available" 