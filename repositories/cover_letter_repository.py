from typing import List, Optional, Dict, Any
from domain.models.cover_letter import CoverLetter, CoverLetterInDB, CoverLetterStatus
from repositories.base import Repository
from core.exceptions import DatabaseError, NotFoundError
from bson import ObjectId
from datetime import datetime

class CoverLetterRepository(Repository[CoverLetterInDB]):
    def __init__(self):
        super().__init__(CoverLetterInDB, "cover_letters")
        # Create indexes for better query performance
        self._create_indexes()

    async def _create_indexes(self):
        """Create necessary indexes for the collection"""
        try:
            await self.collection.create_index("user_id")
            await self.collection.create_index([("user_id", 1), ("status", 1)])
            await self.collection.create_index([("user_id", 1), ("active", 1)])
        except Exception as e:
            raise DatabaseError(f"Failed to create indexes: {str(e)}")

    async def get_by_user(
        self,
        user_id: str,
        page: int = 1,
        per_page: int = 10,
        status: Optional[CoverLetterStatus] = None,
        active: Optional[bool] = None
    ) -> Dict[str, Any]:
        """Get cover letters for a user with pagination and optional filters"""
        try:
            # Build filter
            filter_dict = {"user_id": user_id}
            if status is not None:
                filter_dict["status"] = status
            if active is not None:
                filter_dict["active"] = active

            # Get total count
            total = await self.collection.count_documents(filter_dict)

            # Calculate pagination
            skip = (page - 1) * per_page
            cursor = self.collection.find(filter_dict).skip(skip).limit(per_page).sort("updated_at", -1)
            items = await cursor.to_list(length=per_page)

            # Convert to models
            cover_letters = [CoverLetterInDB(**self._convert_mongo_doc(item)) for item in items]

            return {
                "list": cover_letters,
                "pagination": {
                    "total": total,
                    "current_page": page,
                    "total_pages": (total + per_page - 1) // per_page,
                    "per_page": per_page
                }
            }
        except Exception as e:
            raise DatabaseError(f"Failed to get cover letters: {str(e)}")

    async def get_active_cover_letter(self, user_id: str) -> Optional[CoverLetterInDB]:
        """Get the active cover letter for a user"""
        try:
            data = await self.collection.find_one({
                "user_id": user_id,
                "active": True
            })
            if not data:
                return None
            return CoverLetterInDB(**self._convert_mongo_doc(data))
        except Exception as e:
            raise DatabaseError(f"Failed to get active cover letter: {str(e)}")

    async def deactivate_other_cover_letters(self, user_id: str, exclude_id: str):
        """Deactivate all cover letters except the specified one"""
        try:
            await self.collection.update_many(
                {
                    "user_id": user_id,
                    "_id": {"$ne": ObjectId(exclude_id)},
                    "active": True
                },
                {"$set": {"active": False, "updated_at": datetime.utcnow()}}
            )
        except Exception as e:
            raise DatabaseError(f"Failed to deactivate cover letters: {str(e)}")

    async def update_status(self, id: str, status: CoverLetterStatus) -> CoverLetterInDB:
        """Update the status of a cover letter"""
        try:
            data = await self.collection.find_one_and_update(
                {"_id": ObjectId(id)},
                {
                    "$set": {
                        "status": status,
                        "updated_at": datetime.utcnow()
                    }
                },
                return_document=True
            )
            if not data:
                raise NotFoundError("Cover letter not found")
            return CoverLetterInDB(**self._convert_mongo_doc(data))
        except Exception as e:
            raise DatabaseError(f"Failed to update status: {str(e)}")

    async def search(
        self,
        user_id: str,
        query: str,
        page: int = 1,
        per_page: int = 10
    ) -> Dict[str, Any]:
        """Search cover letters by content"""
        try:
            # Create text index if it doesn't exist
            if "content_text" not in await self.collection.index_information():
                await self.collection.create_index([
                    ("content.introduction", "text"),
                    ("content.body_part_1", "text"),
                    ("content.body_part_2", "text"),
                    ("content.conclusion", "text"),
                    ("name", "text"),
                    ("job_title", "text"),
                    ("company_name", "text")
                ], name="content_text")

            # Build search query
            search_filter = {
                "user_id": user_id,
                "$text": {"$search": query}
            }

            # Get total count
            total = await self.collection.count_documents(search_filter)

            # Calculate pagination
            skip = (page - 1) * per_page
            cursor = self.collection.find(search_filter).skip(skip).limit(per_page).sort("updated_at", -1)
            items = await cursor.to_list(length=per_page)

            # Convert to models
            cover_letters = [CoverLetterInDB(**self._convert_mongo_doc(item)) for item in items]

            return {
                "list": cover_letters,
                "pagination": {
                    "total": total,
                    "current_page": page,
                    "total_pages": (total + per_page - 1) // per_page,
                    "per_page": per_page
                }
            }
        except Exception as e:
            raise DatabaseError(f"Failed to search cover letters: {str(e)}") 