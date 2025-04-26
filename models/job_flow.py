from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from bson import ObjectId

class JobFlowSource(str, Enum):
    INTERNAL = "internal"
    LINKEDIN = "linkedin"

class JobFlowStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"

class JobFlowCreate(BaseModel):
    resume_id: str
    cover_letter_id: str
    job_query_id: str
    source: JobFlowSource
    status: JobFlowStatus = JobFlowStatus.ACTIVE

class JobFlowUpdate(BaseModel):
    resume_id: Optional[str] = None
    cover_letter_id: Optional[str] = None
    job_query_id: Optional[str] = None
    source: Optional[JobFlowSource] = None

class JobFlowStatusUpdate(BaseModel):
    status: JobFlowStatus

class JobFlow(BaseModel):
    id: str
    user_id: str
    resume_id: str
    cover_letter_id: str
    job_query_id: str
    source: JobFlowSource
    status: JobFlowStatus
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda dt: dt.isoformat()
        }
        populate_by_name = True 