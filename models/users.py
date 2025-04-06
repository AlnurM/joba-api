"""User models"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime

class UserBase(BaseModel):
    """Base user model with core fields"""
    login: str
    email: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class UserCreate(UserBase):
    """Model for creating a new user"""
    password: str

class User(UserBase):
    """User model for API responses"""
    id: str = Field(..., alias="_id")
    username: Optional[str] = None
    is_active: bool = True

    class Config:
        from_attributes = True

class UserInDB(User):
    """User model in database"""
    hashed_password: str 