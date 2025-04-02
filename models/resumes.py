from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum

class ResumeStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"

class ResumeBase(BaseModel):
    """Базовая модель резюме"""
    filename: str
    file_id: str  # ID файла в GridFS
    status: ResumeStatus = ResumeStatus.ACTIVE

class ResumeCreate(ResumeBase):
    """Модель для создания нового резюме"""
    pass

class Resume(ResumeBase):
    """Модель резюме для ответов API"""
    id: str
    user_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True 