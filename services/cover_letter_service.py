from typing import List, Optional, Dict, Any
from domain.models.cover_letter import (
    CoverLetter,
    CoverLetterCreate,
    CoverLetterUpdate,
    CoverLetterStatus
)
from repositories.cover_letter_repository import CoverLetterRepository
from core.exceptions import (
    DatabaseError,
    NotFoundError,
    ValidationError,
    BusinessLogicError
)
from datetime import datetime

class CoverLetterService:
    def __init__(self):
        self.repository = CoverLetterRepository()

    async def create_cover_letter(
        self,
        user_id: str,
        cover_letter_data: CoverLetterCreate
    ) -> CoverLetter:
        """Create a new cover letter"""
        try:
            # Convert to dict and add user_id
            data = cover_letter_data.model_dump()
            data["user_id"] = user_id
            data["created_at"] = datetime.utcnow()
            data["updated_at"] = datetime.utcnow()

            # Create the cover letter
            cover_letter = await self.repository.create(data)

            # If this is the first cover letter or it's marked as active,
            # deactivate others and activate this one
            if cover_letter_data.active:
                await self.repository.deactivate_other_cover_letters(
                    user_id,
                    str(cover_letter.id)
                )

            return CoverLetter(**cover_letter.model_dump())
        except Exception as e:
            raise DatabaseError(f"Failed to create cover letter: {str(e)}")

    async def get_cover_letter(
        self,
        user_id: str,
        cover_letter_id: str
    ) -> CoverLetter:
        """Get a cover letter by ID"""
        try:
            cover_letter = await self.repository.get(cover_letter_id)
            if not cover_letter or cover_letter.user_id != user_id:
                raise NotFoundError("Cover letter not found")
            return CoverLetter(**cover_letter.model_dump())
        except Exception as e:
            raise DatabaseError(f"Failed to get cover letter: {str(e)}")

    async def list_cover_letters(
        self,
        user_id: str,
        page: int = 1,
        per_page: int = 10,
        status: Optional[CoverLetterStatus] = None,
        active: Optional[bool] = None
    ) -> Dict[str, Any]:
        """List cover letters with pagination and optional filters"""
        try:
            result = await self.repository.get_by_user(
                user_id,
                page,
                per_page,
                status,
                active
            )
            
            # Convert CoverLetterInDB to CoverLetter
            result["list"] = [
                CoverLetter(**letter.model_dump())
                for letter in result["list"]
            ]
            
            return result
        except Exception as e:
            raise DatabaseError(f"Failed to list cover letters: {str(e)}")

    async def update_cover_letter(
        self,
        user_id: str,
        cover_letter_id: str,
        update_data: CoverLetterUpdate
    ) -> CoverLetter:
        """Update a cover letter"""
        try:
            # Verify ownership
            existing = await self.repository.get(cover_letter_id)
            if not existing or existing.user_id != user_id:
                raise NotFoundError("Cover letter not found")

            # Convert to dict and remove None values
            data = {
                k: v for k, v in update_data.model_dump().items()
                if v is not None
            }

            # Update the cover letter
            updated = await self.repository.update(cover_letter_id, data)

            # Handle active status
            if update_data.active:
                await self.repository.deactivate_other_cover_letters(
                    user_id,
                    cover_letter_id
                )

            return CoverLetter(**updated.model_dump())
        except Exception as e:
            raise DatabaseError(f"Failed to update cover letter: {str(e)}")

    async def delete_cover_letter(
        self,
        user_id: str,
        cover_letter_id: str
    ) -> bool:
        """Delete a cover letter"""
        try:
            # Verify ownership
            existing = await self.repository.get(cover_letter_id)
            if not existing or existing.user_id != user_id:
                raise NotFoundError("Cover letter not found")

            # Delete the cover letter
            return await self.repository.delete(cover_letter_id)
        except Exception as e:
            raise DatabaseError(f"Failed to delete cover letter: {str(e)}")

    async def search_cover_letters(
        self,
        user_id: str,
        query: str,
        page: int = 1,
        per_page: int = 10
    ) -> Dict[str, Any]:
        """Search cover letters by content"""
        try:
            if not query.strip():
                raise ValidationError("Search query cannot be empty")

            result = await self.repository.search(
                user_id,
                query,
                page,
                per_page
            )

            # Convert CoverLetterInDB to CoverLetter
            result["list"] = [
                CoverLetter(**letter.model_dump())
                for letter in result["list"]
            ]

            return result
        except Exception as e:
            raise DatabaseError(f"Failed to search cover letters: {str(e)}")

    async def get_active_cover_letter(
        self,
        user_id: str
    ) -> Optional[CoverLetter]:
        """Get the active cover letter for a user"""
        try:
            cover_letter = await self.repository.get_active_cover_letter(user_id)
            if not cover_letter:
                return None
            return CoverLetter(**cover_letter.model_dump())
        except Exception as e:
            raise DatabaseError(f"Failed to get active cover letter: {str(e)}")

    async def update_status(
        self,
        user_id: str,
        cover_letter_id: str,
        status: CoverLetterStatus
    ) -> CoverLetter:
        """Update the status of a cover letter"""
        try:
            # Verify ownership
            existing = await self.repository.get(cover_letter_id)
            if not existing or existing.user_id != user_id:
                raise NotFoundError("Cover letter not found")

            # Update status
            updated = await self.repository.update_status(cover_letter_id, status)
            return CoverLetter(**updated.model_dump())
        except Exception as e:
            raise DatabaseError(f"Failed to update status: {str(e)}") 