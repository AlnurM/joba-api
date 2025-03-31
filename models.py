from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime

class UserBase(BaseModel):
    email: EmailStr
    username: Optional[str] = None

class UserCreate(UserBase):
    password: str

class UserLogin(BaseModel):
    login: str  # email или username
    password: str

class User(UserBase):
    id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = True

    class Config:
        from_attributes = True

class UserInDB(User):
    hashed_password: str

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    sub: str
    exp: datetime
    type: str  # access или refresh

class AvailabilityCheck(BaseModel):
    email: Optional[str] = None
    username: Optional[str] = None

class AvailabilityResponse(BaseModel):
    available: bool
    message: str 