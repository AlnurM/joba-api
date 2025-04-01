from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class UserLogin(BaseModel):
    """Модель для входа пользователя"""
    login: str  # email или username
    password: str

class Token(BaseModel):
    """Модель токена доступа"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    """Модель данных токена"""
    sub: str
    exp: datetime
    type: str  # access или refresh

class AvailabilityCheck(BaseModel):
    """Модель для проверки доступности email и username"""
    email: Optional[str] = None
    username: Optional[str] = None

class AvailabilityResponse(BaseModel):
    """Модель ответа на проверку доступности"""
    available: bool
    message: str 