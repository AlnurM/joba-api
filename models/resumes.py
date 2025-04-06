"""Models for resumes"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime

class ResumeStatus(str, Enum):
    """Resume status options"""
    ACTIVE = "active"
    ARCHIVED = "archived"

class ResumeStatusUpdate(BaseModel):
    """Model for updating resume status"""
    status: ResumeStatus

class ResumeBase(BaseModel):
    """Base resume model"""
    file_id: str  # File ID in GridFS
    status: ResumeStatus = ResumeStatus.ARCHIVED
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class ResumeCreate(ResumeBase):
    """Model for creating a new resume"""
    pass

class Resume(ResumeBase):
    """Resume model for API responses"""
    id: str = Field(..., alias="_id") 