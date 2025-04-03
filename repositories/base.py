from typing import Generic, TypeVar, Type, Optional, List, Dict, Any, Set
from pydantic import BaseModel
from datetime import datetime
from bson import ObjectId
from core.database import get_db
from core.exceptions import DatabaseError, NotFoundError
from core.security import SecurityConfig

T = TypeVar('T', bound=BaseModel)

class Repository(Generic[T]):
    def __init__(self, model: Type[T], collection_name: str):
        self.model = model
        self.collection_name = collection_name
        self.collection = get_db()[collection_name]
        self._sensitive_fields = self._get_sensitive_fields()

    def _get_sensitive_fields(self) -> Set[str]:
        """Get fields marked as sensitive in the model"""
        sensitive_fields = set()
        for field_name, field in self.model.model_fields.items():
            if field.description and "sensitive" in field.description.lower():
                sensitive_fields.add(field_name)
        return sensitive_fields

    def _convert_mongo_doc(self, doc: Dict[str, Any], include_sensitive: bool = False) -> Dict[str, Any]:
        """Convert MongoDB document to dict suitable for Pydantic model"""
        if not doc:
            return {}
        
        # Convert ObjectId to string
        if '_id' in doc:
            doc['id'] = str(doc.pop('_id'))
        
        # Remove sensitive fields if not explicitly included
        if not include_sensitive:
            for field in self._sensitive_fields:
                doc.pop(field, None)
        
        # Ensure all required fields are present
        model_fields = self.model.model_fields
        for field_name, field_info in model_fields.items():
            if field_info.is_required and field_name not in doc:
                if field_name in self._sensitive_fields and not include_sensitive:
                    continue
                doc[field_name] = field_info.default if hasattr(field_info, 'default') else None
        
        return doc

    async def create(self, data: Dict[str, Any]) -> T:
        try:
            # Ensure sensitive fields are included during creation
            data['created_at'] = datetime.utcnow()
            result = await self.collection.insert_one(data)
            data['id'] = str(result.inserted_id)
            return self.model(**self._convert_mongo_doc(data, include_sensitive=True))
        except Exception as e:
            raise DatabaseError(f"Failed to create {self.collection_name}: {str(e)}")

    async def get(self, id: str, include_sensitive: bool = False) -> Optional[T]:
        try:
            data = await self.collection.find_one({"_id": ObjectId(id)})
            if not data:
                raise NotFoundError(f"{self.collection_name} not found")
            return self.model(**self._convert_mongo_doc(data, include_sensitive))
        except Exception as e:
            raise DatabaseError(f"Failed to get {self.collection_name}: {str(e)}")

    async def list(self, filter_dict: Dict[str, Any] = None, skip: int = 0, limit: int = 10, include_sensitive: bool = False) -> List[T]:
        try:
            cursor = self.collection.find(filter_dict or {}).skip(skip).limit(limit)
            items = await cursor.to_list(length=limit)
            return [self.model(**self._convert_mongo_doc(item, include_sensitive)) for item in items]
        except Exception as e:
            raise DatabaseError(f"Failed to list {self.collection_name}: {str(e)}")

    async def update(self, id: str, data: Dict[str, Any], include_sensitive: bool = False) -> Optional[T]:
        try:
            data['updated_at'] = datetime.utcnow()
            result = await self.collection.find_one_and_update(
                {"_id": ObjectId(id)},
                {"$set": data},
                return_document=True
            )
            if not result:
                raise NotFoundError(f"{self.collection_name} not found")
            return self.model(**self._convert_mongo_doc(result, include_sensitive))
        except Exception as e:
            raise DatabaseError(f"Failed to update {self.collection_name}: {str(e)}")

    async def delete(self, id: str) -> bool:
        try:
            result = await self.collection.delete_one({"_id": ObjectId(id)})
            if result.deleted_count == 0:
                raise NotFoundError(f"{self.collection_name} not found")
            return True
        except Exception as e:
            raise DatabaseError(f"Failed to delete {self.collection_name}: {str(e)}") 