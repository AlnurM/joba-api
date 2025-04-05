from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from bson import ObjectId
from enum import Enum

class CoverLetterStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"

class CoverLetterContent(BaseModel):
    introduction: str
    body_part_1: str
    body_part_2: str
    conclusion: str

class CoverLetterGenerateRequest(BaseModel):
    """Модель для запроса генерации текста сопроводительного письма"""
    resume_id: str
    prompt: str
    content_type: str = Field(
        description="Тип контента: introduction, body_part_1, body_part_2, conclusion"
    )

class CoverLetterCreate(BaseModel):
    content: CoverLetterContent
    name: str
    status: CoverLetterStatus = CoverLetterStatus.ARCHIVED

class CoverLetterStatusUpdate(BaseModel):
    """Модель для обновления статуса сопроводительного письма"""
    status: CoverLetterStatus

class CoverLetter(BaseModel):
    id: str
    user_id: str
    name: str
    content: CoverLetterContent
    status: CoverLetterStatus = CoverLetterStatus.ARCHIVED
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True

    class Config:
        json_encoders = {
            ObjectId: str,
            datetime: lambda dt: dt.isoformat()
        }
        populate_by_name = True 