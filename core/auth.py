from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
import os
import logging
from models import User, UserCreate, AccessToken
from core.database import get_db
from bson.objectid import ObjectId
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer

# Logging setup
logger = logging.getLogger(__name__)

# Security settings
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24  # Changed from 30 minutes to 24 hours
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Password hashing settings
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# HTTPBearer initialization
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
    """Create a new user"""
    db = get_db()
    
    # Check if user with this email exists
    if await db.users.find_one({"email": user.email}):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered"
        )
    
    # Check if user with this username exists (if provided)
    if user.username and await db.users.find_one({"username": user.username}):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken"
        )
    
    try:
        # Create new user
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
    """Authenticate user by email or username"""
    try:
        db = get_db()
        
        # Search for user by email or username
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
        
        # Convert ObjectId to string for id and prepare user data
        user_data = {
            "id": str(user["_id"]),
            "email": user["email"],
            "username": user.get("username"),
            "created_at": user.get("created_at", datetime.utcnow()),
            "updated_at": user.get("updated_at", datetime.utcnow())
        }
        
        return User(**user_data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during authentication: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication error"
        )

async def get_current_user(token: str = Depends(security)) -> User:
    """Get current user by token"""
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
        # Convert string ID to ObjectId
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if user is None:
            raise credentials_exception
        
        # Convert ObjectId to string for id
        user["id"] = str(user["_id"])
        # Remove _id as it's not needed in the model
        del user["_id"]
        return User(**user)
    except Exception as e:
        logger.error(f"Error getting user: {str(e)}")
        raise credentials_exception

async def refresh_access_token(refresh_token: str) -> str:
    """Refresh access token using refresh token"""
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
        # Check if user exists
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Create new access token
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
    Check email and username availability.
    
    Args:
        email: Email to check
        username: Username to check
        
    Returns:
        Dict[str, Any]: {"is_available": bool, "message": str}
    """
    try:
        db = get_db()
        
        # Если ни email, ни username не предоставлены, вернуть ошибку
        if not email and not username:
            return {
                "is_available": False,
                "message": "No email or username provided"
            }
            
        result = {
            "is_available": True,
            "message": "Available"
        }
        
        # Проверяем email, если он предоставлен
        if email:
            email_exists = await db.users.find_one({"email": email})
            if email_exists:
                return {
                    "is_available": False,
                    "message": "Email already registered"
                }
        
        # Проверяем username, если он предоставлен
        if username:
            username_exists = await db.users.find_one({"username": username})
            if username_exists:
                return {
                    "is_available": False,
                    "message": "Username already taken"
                }
        
        return result
    except Exception as e:
        logger.error(f"Error checking availability: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error checking availability"
        ) 