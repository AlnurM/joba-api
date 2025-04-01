from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime

class UserBase(BaseModel):
    """Базовая модель пользователя с основными полями"""
    email: EmailStr
    username: Optional[str] = None

class UserCreate(UserBase):
    """Модель для создания нового пользователя"""
    password: str

class User(UserBase):
    """Модель пользователя для ответов API"""
    id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = True

    class Config:
        from_attributes = True

class UserInDB(User):
    """Модель пользователя в базе данных"""
    hashed_password: str 