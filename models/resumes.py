"""Models for resumes"""

from enum import Enum
from typing import Optional, Dict, Any
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

class Resume(BaseModel):
    """Resume model with scoring fields"""
    id: str = Field(..., alias="_id")
    user_id: str
    filename: str
    file_id: Optional[str] = None
    status: ResumeStatus = ResumeStatus.ARCHIVED
    created_at: datetime
    updated_at: datetime
    candidate: Dict[str, Any]
    
    # Scoring fields
    scoring: Optional[Dict[str, float]] = Field(None, description="Resume scoring results")
    feedback: Optional[Dict[str, str]] = Field(None, description="Detailed feedback for each scoring category")
    
    class Config:
        allow_population_by_field_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        } 