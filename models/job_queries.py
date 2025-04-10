from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from bson import ObjectId

class JobQueryStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"

class JobQueryKeywords(BaseModel):
    job_titles: List[str]
    required_skills: List[str]
    work_arrangements: List[str]
    positions: List[str]
    exclude_words: List[str]

class JobQueryCreate(BaseModel):
    name: str
    keywords: JobQueryKeywords
    query: str = ""
    status: JobQueryStatus = JobQueryStatus.ARCHIVED

class JobQueryUpdate(BaseModel):
    name: Optional[str] = None
    keywords: Optional[JobQueryKeywords] = None
    query: Optional[str] = None

class JobQueryStatusUpdate(BaseModel):
    status: JobQueryStatus

class JobQuery(BaseModel):
    id: str
    user_id: str
    name: str
    keywords: JobQueryKeywords
    query: str
    status: JobQueryStatus
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda dt: dt.isoformat()
        }
        populate_by_name = True

# Существующие модели
class JobQueryGenerateRequest(BaseModel):
    resume_id: str

class JobQueryResponse(BaseModel):
    keywords: JobQueryKeywords 