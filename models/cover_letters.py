from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from bson import ObjectId

class CoverLetterContent(BaseModel):
    introduction: str
    body_part_1: str
    body_part_2: str
    conclusion: str

class CoverLetterCreate(BaseModel):
    content: CoverLetterContent
    name: str
    active: bool = False

class CoverLetter(CoverLetterCreate):
    id: Optional[str] = Field(alias="_id")
    userId: str
    createdAt: datetime = Field(default_factory=datetime.utcnow)
    updatedAt: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {
            ObjectId: str,
            datetime: lambda dt: dt.isoformat()
        }
        populate_by_name = True 