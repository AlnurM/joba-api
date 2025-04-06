"""Models for cover letters"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime
from bson import ObjectId

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
    """Model for cover letter content generation request"""
    resume_id: str
    prompt: str
    content_type: str = Field(
        description="Content type: introduction, body_part_1, body_part_2, conclusion"
    )

class CoverLetterCreate(BaseModel):
    content: CoverLetterContent
    name: str
    status: CoverLetterStatus = CoverLetterStatus.ARCHIVED

class CoverLetterStatusUpdate(BaseModel):
    """Model for updating cover letter status"""
    status: CoverLetterStatus

class CoverLetter(BaseModel):
    id: str
    user_id: str
    name: str
    content: CoverLetterContent
    status: CoverLetterStatus = CoverLetterStatus.ARCHIVED
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class CoverLetter(CoverLetterBase):
    """Cover letter model for API responses"""
    id: str = Field(..., alias="_id")

    class Config:
        from_attributes = True

    class Config:
        json_encoders = {
            ObjectId: str,
            datetime: lambda dt: dt.isoformat()
        }
        populate_by_name = True 