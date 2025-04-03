from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional, Dict, Any
from domain.models.cover_letter import (
    CoverLetter,
    CoverLetterCreate,
    CoverLetterUpdate,
    CoverLetterStatus
)
from domain.models.user import User
from services.cover_letter_service import CoverLetterService
from core.auth import get_current_user
from core.exceptions import (
    DatabaseError,
    NotFoundError,
    ValidationError,
    BusinessLogicError
)

router = APIRouter()

def get_cover_letter_service() -> CoverLetterService:
    return CoverLetterService()

@router.post("", response_model=CoverLetter, status_code=status.HTTP_201_CREATED)
async def create_cover_letter(
    cover_letter: CoverLetterCreate,
    current_user: User = Depends(get_current_user),
    service: CoverLetterService = Depends(get_cover_letter_service)
):
    """Create a new cover letter"""
    try:
        return await service.create_cover_letter(str(current_user.id), cover_letter)
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except DatabaseError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/active", response_model=Optional[CoverLetter])
async def get_active_cover_letter(
    current_user: User = Depends(get_current_user),
    service: CoverLetterService = Depends(get_cover_letter_service)
):
    """Get the active cover letter for the current user"""
    try:
        return await service.get_active_cover_letter(str(current_user.id))
    except DatabaseError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/{cover_letter_id}", response_model=CoverLetter)
async def get_cover_letter(
    cover_letter_id: str,
    current_user: User = Depends(get_current_user),
    service: CoverLetterService = Depends(get_cover_letter_service)
):
    """Get a cover letter by ID"""
    try:
        return await service.get_cover_letter(str(current_user.id), cover_letter_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DatabaseError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("", response_model=Dict[str, Any])
async def list_cover_letters(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    status: Optional[CoverLetterStatus] = None,
    active: Optional[bool] = None,
    current_user: User = Depends(get_current_user),
    service: CoverLetterService = Depends(get_cover_letter_service)
):
    """List cover letters with pagination and optional filters"""
    try:
        return await service.list_cover_letters(
            str(current_user.id),
            page,
            per_page,
            status,
            active
        )
    except DatabaseError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.put("/{cover_letter_id}", response_model=CoverLetter)
async def update_cover_letter(
    cover_letter_id: str,
    cover_letter: CoverLetterUpdate,
    current_user: User = Depends(get_current_user),
    service: CoverLetterService = Depends(get_cover_letter_service)
):
    """Update a cover letter"""
    try:
        return await service.update_cover_letter(
            str(current_user.id),
            cover_letter_id,
            cover_letter
        )
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except DatabaseError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.delete("/{cover_letter_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cover_letter(
    cover_letter_id: str,
    current_user: User = Depends(get_current_user),
    service: CoverLetterService = Depends(get_cover_letter_service)
):
    """Delete a cover letter"""
    try:
        await service.delete_cover_letter(str(current_user.id), cover_letter_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DatabaseError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/search", response_model=Dict[str, Any])
async def search_cover_letters(
    query: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    service: CoverLetterService = Depends(get_cover_letter_service)
):
    """Search cover letters by content"""
    try:
        return await service.search_cover_letters(
            str(current_user.id),
            query,
            page,
            per_page
        )
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except DatabaseError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.patch("/{cover_letter_id}/status", response_model=CoverLetter)
async def update_status(
    cover_letter_id: str,
    status: CoverLetterStatus,
    current_user: User = Depends(get_current_user),
    service: CoverLetterService = Depends(get_cover_letter_service)
):
    """Update the status of a cover letter"""
    try:
        return await service.update_status(
            str(current_user.id),
            cover_letter_id,
            status
        )
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DatabaseError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) 