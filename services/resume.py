from typing import List, Optional, Dict, Any
from fastapi import UploadFile
from repositories.base import Repository
from domain.models import Resume
from services.storage import StorageService
from core.exceptions import NotFoundError, ValidationError

class ResumeService:
    def __init__(self):
        self.repository = Repository(Resume, "resumes")
        self.storage = StorageService()

    async def create(self, file: UploadFile, user_id: str) -> Resume:
        """Create a new resume"""
        filename, file_id = await self.storage.save(file, user_id)
        return await self.repository.create({
            "user_id": user_id,
            "filename": filename,
            "file_id": file_id
        })

    async def get(self, resume_id: str, user_id: str) -> Resume:
        """Get a resume by ID and user ID"""
        resume = await self.repository.get(resume_id)
        if not resume or resume.user_id != user_id:
            raise NotFoundError("Resume not found")
        return resume

    async def get_user_resumes(self, user_id: str, skip: int = 0, limit: int = 10) -> List[Resume]:
        """Get all resumes for a user"""
        return await self.repository.list({"user_id": user_id}, skip, limit)

    async def get_resume_file(self, resume_id: str, user_id: str) -> tuple[bytes, str]:
        """Get resume file content"""
        resume = await self.get(resume_id, user_id)
        return await self.storage.get(resume.file_id)

    async def update_status(self, resume_id: str, user_id: str, status: str) -> Resume:
        """Update resume status"""
        resume = await self.get(resume_id, user_id)
        return await self.repository.update(resume_id, {"status": status})

    async def delete(self, resume_id: str, user_id: str) -> bool:
        """Delete a resume"""
        resume = await self.get(resume_id, user_id)
        return await self.repository.delete(resume_id) 