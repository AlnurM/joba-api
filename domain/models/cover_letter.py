from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime
from enum import Enum
from bson import ObjectId

class CoverLetterStatus(str, Enum):
    """Status of a cover letter"""
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"

class CoverLetterContent(BaseModel):
    """Structured content of a cover letter"""
    introduction: str = Field(..., min_length=1, description="Introduction paragraph")
    body_part_1: str = Field(..., min_length=1, description="First body paragraph")
    body_part_2: str = Field(..., min_length=1, description="Second body paragraph")
    conclusion: str = Field(..., min_length=1, description="Conclusion paragraph")

    @validator('*')
    def validate_paragraph_length(cls, v):
        """Validate that each paragraph is not too long"""
        if len(v) > 2000:  # Reasonable limit for a paragraph
            raise ValueError("Paragraph is too long")
        return v

class CoverLetterBase(BaseModel):
    """Base cover letter model with core fields"""
    name: str = Field(..., min_length=1, max_length=100, description="Name of the cover letter")
    content: CoverLetterContent = Field(..., description="Structured content of the cover letter")
    status: CoverLetterStatus = Field(default=CoverLetterStatus.DRAFT, description="Status of the cover letter")
    job_title: Optional[str] = Field(None, max_length=100, description="Target job title")
    company_name: Optional[str] = Field(None, max_length=100, description="Target company name")
    tags: List[str] = Field(default_factory=list, description="Tags for categorizing the cover letter")
    active: bool = Field(default=False, description="Whether the cover letter is active")

    @validator('tags')
    def validate_tags(cls, v):
        """Validate that tags are unique and have reasonable length"""
        v = list(set(v))  # Remove duplicates
        for tag in v:
            if len(tag) > 50:
                raise ValueError("Tag is too long")
        return v

class CoverLetterCreate(CoverLetterBase):
    """Model for creating a new cover letter"""
    pass

class CoverLetterUpdate(BaseModel):
    """Model for updating an existing cover letter"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    content: Optional[CoverLetterContent] = None
    status: Optional[CoverLetterStatus] = None
    job_title: Optional[str] = Field(None, max_length=100)
    company_name: Optional[str] = Field(None, max_length=100)
    tags: Optional[List[str]] = None
    active: Optional[bool] = None

    @validator('tags')
    def validate_tags(cls, v):
        if v is not None:
            v = list(set(v))
            for tag in v:
                if len(tag) > 50:
                    raise ValueError("Tag is too long")
        return v

class CoverLetterInDB(CoverLetterBase):
    """Model for cover letter in database"""
    id: str = Field(..., description="Cover letter's unique identifier")
    user_id: str = Field(..., description="ID of the user who owns this cover letter")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")

class CoverLetter(CoverLetterBase):
    """Model for API responses"""
    id: str = Field(..., description="Cover letter's unique identifier")
    user_id: str = Field(..., description="ID of the user who owns this cover letter")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    class Config:
        from_attributes = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda dt: dt.isoformat()
        }
        populate_by_name = True 