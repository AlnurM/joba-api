from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
from core.security import SecurityConfig

class UserBase(BaseModel):
    """Base user model with core fields"""
    email: EmailStr = Field(..., description="User's email address")
    username: Optional[str] = Field(None, description="User's username")
    is_active: bool = Field(True, description="Whether the user account is active")
    is_superuser: bool = Field(False, description="Whether the user has admin privileges")

class UserCreate(UserBase):
    """Model for creating a new user"""
    password: str = Field(..., description="User's password (will be hashed before storage)")

    def __init__(self, **data):
        super().__init__(**data)
        SecurityConfig.validate_password(self.password)

class UserInDB(UserBase):
    """Model for user in database"""
    id: str = Field(..., description="User's unique identifier")
    password: str = Field(..., description="Hashed password (sensitive)")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Account creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")

class User(UserBase):
    """Model for API responses"""
    id: str = Field(..., description="User's unique identifier")
    created_at: datetime = Field(..., description="Account creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")

    class Config:
        from_attributes = True 