from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from motor.motor_asyncio import AsyncIOMotorDatabase
from models import User, UserCreate, UserLogin, Token
from bson import ObjectId
import os
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
import logging

load_dotenv()

# Настройки JWT
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Настройки хеширования паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 схема
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="signin")

# Глобальная переменная для базы данных
db: Optional[AsyncIOMotorDatabase] = None

# Настройка логирования
logger = logging.getLogger(__name__)

# Инициализация подключения к базе данных
async def init_db():
    global db
    try:
        mongodb_url = os.getenv("MONGO_URL")
        if not mongodb_url:
            logger.error("MONGO_URL не установлен в переменных окружения")
            raise ValueError("MONGO_URL не установлен в переменных окружения")
        
        logger.info(f"Attempting to connect to MongoDB with URL: {mongodb_url}")
        client = AsyncIOMotorClient(
            mongodb_url,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000
        )
        
        # Проверяем подключение
        await client.admin.command('ping')
        logger.info("Successfully pinged MongoDB server")
        
        db = client.joba
        logger.info("Successfully initialized database connection")
        
        # Проверяем доступ к коллекции users
        await db.users.find_one()
        logger.info("Successfully accessed users collection")
        
    except Exception as e:
        logger.error(f"Failed to initialize database: {str(e)}")
        raise

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if user is None:
        raise credentials_exception
    return User(**user)

async def authenticate_user(login: str, password: str) -> Optional[User]:
    logger.info(f"Searching for user with login: {login}")
    # Пытаемся найти пользователя по email или username
    query = {
        "$or": [
            {"email": login},
            {"username": login}
        ]
    }
    logger.info(f"MongoDB query: {query}")
    user = await db.users.find_one(query)
    
    if not user:
        logger.warning(f"User not found with login: {login}")
        return None
    
    logger.info(f"User found: {user}")
    if not verify_password(password, user["hashed_password"]):
        logger.warning("Password verification failed")
        return None
    
    # Преобразуем _id в id
    user_dict = {
        "id": str(user["_id"]),
        "email": user["email"],
        "username": user.get("username"),
        "hashed_password": user["hashed_password"],
        "is_active": user.get("is_active", True),
        "created_at": user.get("created_at", datetime.utcnow())
    }
    
    logger.info("User authenticated successfully")
    return User(**user_dict)

async def get_user_by_email(email: str) -> Optional[User]:
    user = await db.users.find_one({"email": email})
    if user:
        return User(**user)
    return None

async def create_user(user: UserCreate) -> User:
    # Проверяем, существует ли пользователь с таким email
    if await get_user_by_email(user.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Создаем нового пользователя
    user_dict = user.model_dump()
    user_dict["hashed_password"] = get_password_hash(user_dict.pop("password"))
    
    result = await db.users.insert_one(user_dict)
    user_dict["id"] = str(result.inserted_id)
    return User(**user_dict) 