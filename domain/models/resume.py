from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from enum import Enum

class ResumeStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class Resume(BaseModel):
    id: str
    user_id: str
    filename: str
    file_id: str
    status: ResumeStatus = ResumeStatus.PENDING
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True 