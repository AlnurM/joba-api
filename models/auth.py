"""Authentication models"""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class SignInRequest(BaseModel):
    """Model for user sign in"""
    login: str  # email or username
    password: str

class AccessToken(BaseModel):
    """Access token model"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    """Token data model"""
    user_id: str
    type: str  # access or refresh
    exp: int

class AvailabilityCheck(BaseModel):
    """Model for checking email and username availability"""
    email: Optional[str] = None
    username: Optional[str] = None

class AvailabilityResponse(BaseModel):
    """Response model for availability check"""
    is_available: bool
    message: str 