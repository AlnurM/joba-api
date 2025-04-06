from fastapi import APIRouter, Depends, HTTPException, status, Header
from typing import List, Optional
from models.cover_letters import (
    CoverLetter, CoverLetterCreate, CoverLetterStatus,
    CoverLetterStatusUpdate, CoverLetterGenerateRequest,
    CoverLetterRenderRequest, CoverLetterContent, CoverLetterUpdate
)
from models.resumes import Resume
from core.auth import get_current_user
from models.users import User
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import os
from typing import Dict, Any
from core.database import get_db
from datetime import datetime
from core.claude_client import ClaudeClient

router = APIRouter(tags=["cover-letters"])

async def get_cover_letters_by_user(
    user_id: str,
    page: int = 1,
    per_page: int = 10
) -> Dict[str, Any]:
    """
    Get user's cover letters with pagination
    """
    skip = (page - 1) * per_page
    db = get_db()
    
    # Get total number of documents
    total = await db.cover_letters.count_documents({"user_id": user_id})
    
    # Get documents with pagination
    cursor = db.cover_letters.find({"user_id": user_id}).sort([
        ("status", 1),  # 1 for ascending, to have "active" first (since active < archived alphabetically)
        ("created_at", -1)  # -1 for descending, to have newest first
    ]).skip(skip).limit(per_page)
    cover_letters = await cursor.to_list(length=per_page)
    
    # Convert ObjectId to strings
    processed_letters = []
    for letter in cover_letters:
        letter_dict = {
            "id": str(letter["_id"]),
            "user_id": letter["user_id"],
            "name": letter["name"],
            "content": letter["content"],
            "status": letter.get("status", CoverLetterStatus.ARCHIVED),
            "created_at": letter.get("created_at", datetime.utcnow()),
            "updated_at": letter.get("updated_at", datetime.utcnow())
        }
        processed_letters.append(letter_dict)
    
    return {
        "list": processed_letters,
        "pagination": {
            "total": total,
            "currentPage": page,
            "totalPages": (total + per_page - 1) // per_page,
            "perPage": per_page
        }
    }

@router.get("/list", response_model=Dict[str, Any])
async def list_cover_letters(
    page: int = 1,
    per_page: int = 10,
    current_user: User = Depends(get_current_user)
):
    """
    Get current user's cover letters list with pagination
    """
    try:
        return await get_cover_letters_by_user(
            user_id=str(current_user.id),
            page=page,
            per_page=per_page
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("", response_model=CoverLetter)
async def create_cover_letter(
    cover_letter: CoverLetterCreate,
    current_user: User = Depends(get_current_user)
):
    """
    Create a new cover letter
    """
    try:
        db = get_db()
        
        # Add system fields
        cover_letter_dict = cover_letter.model_dump()
        cover_letter_dict.update({
            "user_id": str(current_user.id),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        })
        
        # Save to database
        result = await db.cover_letters.insert_one(cover_letter_dict)
        
        # Get created document
        created_letter = await db.cover_letters.find_one({"_id": result.inserted_id})
        created_letter["id"] = str(created_letter.pop("_id"))
        
        return CoverLetter(**created_letter)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/{cover_letter_id}", response_model=CoverLetter)
async def get_cover_letter(
    cover_letter_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get cover letter by ID.
    Checks that the document belongs to the current user.
    """
    try:
        db = get_db()
        
        # Check ObjectId validity
        try:
            object_id = ObjectId(cover_letter_id)
        except:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid cover letter ID format"
            )
        
        # Find document and check user ownership
        cover_letter = await db.cover_letters.find_one({
            "_id": object_id,
            "user_id": str(current_user.id)
        })
        
        if not cover_letter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cover letter not found or access denied"
            )
        
        # Convert ObjectId to string
        cover_letter["id"] = str(cover_letter.pop("_id"))
        
        return CoverLetter(**cover_letter)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.patch("/{cover_letter_id}/status", response_model=CoverLetter)
async def update_cover_letter_status(
    cover_letter_id: str,
    status_update: CoverLetterStatusUpdate,
    current_user: User = Depends(get_current_user)
):
    """
    Update cover letter status
    """
    try:
        db = get_db()
        
        # Check ObjectId validity
        try:
            object_id = ObjectId(cover_letter_id)
        except:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid cover letter ID format"
            )
        
        # Check document existence and access rights
        cover_letter = await db.cover_letters.find_one({
            "_id": object_id,
            "user_id": str(current_user.id)
        })
        
        if not cover_letter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cover letter not found or access denied"
            )
        
        # Update status
        result = await db.cover_letters.update_one(
            {"_id": object_id},
            {
                "$set": {
                    "status": status_update.status,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        if result.modified_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cover letter not updated"
            )
        
        # Get updated document
        updated_letter = await db.cover_letters.find_one({"_id": object_id})
        updated_letter["id"] = str(updated_letter.pop("_id"))
        
        return CoverLetter(**updated_letter)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.delete("/{cover_letter_id}", status_code=status.HTTP_200_OK)
async def delete_cover_letter(
    cover_letter_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Delete cover letter
    """
    try:
        db = get_db()
        
        # Check ObjectId validity
        try:
            object_id = ObjectId(cover_letter_id)
        except:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid cover letter ID format"
            )
        
        # Check document existence and access rights
        cover_letter = await db.cover_letters.find_one({
            "_id": object_id,
            "user_id": str(current_user.id)
        })
        
        if not cover_letter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cover letter not found or access denied"
            )
        
        # Delete document
        result = await db.cover_letters.delete_one({"_id": object_id})
        
        if result.deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cover letter not deleted"
            )
        
        return {"message": "Cover letter successfully deleted", "id": cover_letter_id}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/generate")
async def generate_cover_letter_content(
    request: CoverLetterGenerateRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Generate cover letter text based on resume data
    
    Args:
        request: Text generation request
        current_user: Current user
        
    Returns:
        Generated text
    """
    try:
        db = get_db()
        claude_client = ClaudeClient()
        
        # Check ObjectId validity
        try:
            resume_id = ObjectId(request.resume_id)
        except:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid resume ID format"
            )
        
        # Get resume and check access rights
        resume = await db.resumes.find_one({
            "_id": resume_id,
            "user_id": str(current_user.id)
        })
        
        if not resume:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resume not found or access denied"
            )
        
        # Check if content_type is valid
        if request.content_type not in ["introduction", "body_part_1", "body_part_2", "conclusion"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid content type"
            )
        
        # Extract candidate data from resume, excluding service fields
        candidate_data = {
            k: v for k, v in resume.items() 
            if k not in ["_id", "user_id", "filename", "file_id", "status", "created_at", "updated_at"]
        }
        
        # Generate text using Claude
        generated_text = await claude_client.generate_cover_letter_content(
            candidate_data=candidate_data,
            prompt=request.prompt,
            content_type=request.content_type
        )
        
        return {"text": generated_text}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/render")
async def render_cover_letter(
    request: CoverLetterRenderRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Render cover letter by filling placeholders based on job description
    
    Args:
        request: Render request with job description and content
        current_user: Current user
        
    Returns:
        Rendered text with filled placeholders
    """
    try:
        claude_client = ClaudeClient()
        
        # Convert content to dict for processing
        content_dict = request.content.model_dump()
        
        # Render text using Claude
        rendered_text = await claude_client.render_cover_letter(
            job_description=request.job_description,
            content=content_dict
        )
        
        return {"text": rendered_text}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.patch("/{cover_letter_id}", response_model=CoverLetter)
async def update_cover_letter(
    cover_letter_id: str,
    update_data: CoverLetterUpdate,
    current_user: User = Depends(get_current_user)
):
    """
    Update cover letter content and name
    """
    try:
        db = get_db()
        
        # Check ObjectId validity
        try:
            object_id = ObjectId(cover_letter_id)
        except:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid cover letter ID format"
            )
        
        # Check document existence and access rights
        cover_letter = await db.cover_letters.find_one({
            "_id": object_id,
            "user_id": str(current_user.id)
        })
        
        if not cover_letter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cover letter not found or access denied"
            )
        
        # Update document
        result = await db.cover_letters.update_one(
            {"_id": object_id},
            {
                "$set": {
                    "content": update_data.content.model_dump(),
                    "name": update_data.name,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        if result.modified_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cover letter not updated"
            )
        
        # Get updated document
        updated_letter = await db.cover_letters.find_one({"_id": object_id})
        updated_letter["id"] = str(updated_letter.pop("_id"))
        
        return CoverLetter(**updated_letter)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        ) 