from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
import os
import logging
from models import User, UserCreate, Token
from core.database import get_db
from bson.objectid import ObjectId
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer

# Настройка логирования
logger = logging.getLogger(__name__)

# Настройки безопасности
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24  # Изменено с 30 минут на 24 часа
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Настройка хеширования паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Инициализация HTTPBearer
security = HTTPBearer()

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def create_user(user: UserCreate) -> User:
    """Создание нового пользователя"""
    db = get_db()
    
    # Проверяем, существует ли пользователь с таким email
    if await db.users.find_one({"email": user.email}):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered"
        )
    
    # Проверяем, существует ли пользователь с таким username (если указан)
    if user.username and await db.users.find_one({"username": user.username}):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken"
        )
    
    try:
        # Создаем нового пользователя
        hashed_password = get_password_hash(user.password)
        user_dict = user.dict()
        user_dict["password"] = hashed_password
        user_dict["created_at"] = datetime.utcnow()
        
        result = await db.users.insert_one(user_dict)
        user_dict["id"] = str(result.inserted_id)
        return User(**user_dict)
    except Exception as e:
        logger.error(f"Error creating user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating user"
        )

async def authenticate_user(login: str, password: str) -> Optional[User]:
    """Аутентификация пользователя по email или username"""
    try:
        db = get_db()
        
        # Ищем пользователя по email или username
        user = await db.users.find_one({
            "$or": [
                {"email": login},
                {"username": login}
            ]
        })
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect login or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        if not verify_password(password, user["password"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect login or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        user["id"] = str(user["_id"])
        return User(**user)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during authentication: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication error"
        )

async def get_current_user(token: str = Depends(security)) -> User:
    """Получение текущего пользователя по токену"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError as e:
        logger.error(f"JWT Error: {str(e)}")
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
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        db = get_db()
        # Проверяем, существует ли пользователь
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Создаем новый access token
        access_token_expires = timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
        access_token = create_access_token(
            data={"sub": str(user_id)}, expires_delta=access_token_expires
        )
        return access_token
    except JWTError as e:
        logger.error(f"JWT Error in refresh_token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        logger.error(f"Error in refresh_token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error refreshing token"
        )

async def check_availability(email: Optional[str] = None, username: Optional[str] = None) -> Dict[str, Any]:
    """
    Проверяет доступность email и username.
    
    Args:
        email: Email для проверки
        username: Имя пользователя для проверки
        
    Returns:
        Dict[str, Any]: {"available": bool, "message": str}
    """
    try:
        db = get_db()
        
        if email and await db.users.find_one({"email": email}):
            return {
                "available": False,
                "message": "Email already registered"
            }
        
        if username and await db.users.find_one({"username": username}):
            return {
                "available": False,
                "message": "Username already taken"
            }
        
        return {
            "available": True,
            "message": "Available"
        }
    except Exception as e:
        logger.error(f"Error checking availability: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error checking availability"
        ) 