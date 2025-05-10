"""User models"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
from bson import ObjectId

class UserBase(BaseModel):
    """Base user model with core fields"""
    email: str
    username: Optional[str] = None
    onboarding: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class UserCreate(UserBase):
    """Model for creating a new user"""
    password: str

class User(UserBase):
    """User model for API responses"""
    id: str

    class Config:
        from_attributes = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda dt: dt.isoformat()
        }
        populate_by_name = True

class UserInDB(User):
    """User model in database"""
    hashed_password: str 