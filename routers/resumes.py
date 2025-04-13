from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status, Response, Form
from models import Resume, User, ResumeStatusUpdate, ResumeScoringRequest
from models.resumes import ResumeStatus
from core.auth import get_current_user
from core.storage import save_file_content, get_file, is_allowed_file, ALLOWED_EXTENSIONS
from core.database import get_db
from core.resume_processor import process_resume
from core.claude_client import ClaudeClient
from datetime import datetime
import logging
from typing import Dict, Any, Optional
from bson import ObjectId
import os
from motor.motor_asyncio import AsyncIOMotorGridFSBucket

router = APIRouter(tags=["resumes"])
logger = logging.getLogger(__name__)

async def get_resumes_by_user(
    user_id: str,
    page: int = 1,
    per_page: int = 10,
    status: Optional[ResumeStatus] = None
) -> Dict[str, Any]:
    """
    Get user's resumes with pagination.
    Sort by status (active first) and creation date (newest to oldest).
    
    Args:
        user_id: User ID
        page: Page number
        per_page: Items per page
        status: Optional resume status filter
    """
    skip = (page - 1) * per_page
    db = get_db()
    
    # Form search conditions
    query = {"user_id": str(user_id)}
    if status is not None:
        query["status"] = status
    
    # Get total number of documents
    total = await db.resumes.count_documents(query)
    
    # Get documents with pagination and sorting:
    # 1. By status (active first)
    # 2. By creation date (newest to oldest)
    cursor = db.resumes.find(query).sort([
        ("status", 1),  # 1 for ascending, to have "active" first (since active < archived alphabetically)
        ("created_at", -1)  # -1 for descending, to have newest first
    ]).skip(skip).limit(per_page)
    resumes = await cursor.to_list(length=per_page)
    
    # Convert ObjectId to strings and create dictionaries for each resume
    processed_resumes = []
    for resume in resumes:
        resume_dict = {
            "id": str(resume["_id"]),
            "user_id": str(resume["user_id"]),
            "filename": resume["filename"],
            "file_id": resume.get("file_id", ""),
            "status": resume.get("status", ResumeStatus.ARCHIVED),
            "created_at": resume.get("created_at", datetime.utcnow()),
            "scoring": resume.get("scoring", {
                "total_score": 0,
                "sections_score": 0,
                "experience_score": 0,
                "education_score": 0,
                "timeline_score": 0,
                "language_score": 0
            })
        }
        processed_resumes.append(resume_dict)
    
    return {
        "list": processed_resumes,
        "pagination": {
            "total": total,
            "currentPage": page,
            "totalPages": (total + per_page - 1) // per_page,
            "perPage": per_page
        }
    }

@router.post("/upload", response_model=Resume)
async def upload_resume(
    file: UploadFile = File(...),
    status: ResumeStatus = ResumeStatus.ARCHIVED,
    current_user: User = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Upload resume and save it to database.
    
    Args:
        file: Resume file
        status: Optional resume status (default: ARCHIVED)
        current_user: Current user
        db: Database connection
        
    Returns:
        Resume with information about uploaded resume
    """
    try:
        # Check file extension
        file_extension = os.path.splitext(file.filename)[1].lower()
        if file_extension not in ['.pdf', '.doc', '.docx']:
            raise HTTPException(
                status_code=400,
                detail="Unsupported file format. Only PDF, DOC and DOCX are supported"
            )
            
        # Read file content
        file_content = await file.read()
        
        # Save file to GridFS
        file_id = await save_file_content(file_content, file.filename, str(current_user.id))
        
        # Process resume
        logger.info(f"Starting resume processing {file.filename}")
        processed_data = await process_resume(file_content, file_extension)
        
        # Add system fields
        resume_data = {
            **processed_data,
            "user_id": str(current_user.id),
            "filename": file.filename,
            "file_id": file_id,
            "status": status,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        # Save to database
        result = await db.resumes.insert_one(resume_data)
        
        # Получаем созданное резюме и преобразуем его для возврата
        created_resume = await db.resumes.find_one({"_id": result.inserted_id})
        
        # Создаем словарь для ответа, сохраняя _id как строку
        resume_dict = dict(created_resume)
        resume_dict["_id"] = str(result.inserted_id)  # Сохраняем _id как строку
        
        logger.info(f"Resume successfully saved to database, ID: {resume_dict['_id']}")
        
        return Resume(**resume_dict)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading resume: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error uploading resume: {str(e)}"
        )

@router.get("/list", response_model=Dict[str, Any])
async def list_resumes(
    page: int = 1,
    per_page: int = 10,
    status: Optional[ResumeStatus] = None,
    current_user: User = Depends(get_current_user)
):
    """
    Get current user's resume list with pagination and status filtering
    """
    try:
        return await get_resumes_by_user(
            user_id=str(current_user.id),
            page=page,
            per_page=per_page,
            status=status
        )
    except Exception as e:
        logger.error(f"Error getting resume list: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error getting resume list"
        )

@router.get("/{resume_id}/download")
async def download_resume(
    resume_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Download resume
    """
    try:
        # Get resume information
        db = get_db()
        resume = await db.resumes.find_one({
            "_id": ObjectId(resume_id),
            "user_id": str(current_user.id)
        })
        
        if not resume:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resume not found"
            )
        
        # Get file from GridFS
        file_content, filename = await get_file(resume["file_id"])
        
        # Return file
        return Response(
            content=file_content,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading resume: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error downloading resume: {str(e)}"
        )

@router.post("/test-process")
async def test_process_resume(
    file: UploadFile = File(...),
):
    """
    Test endpoint for resume analysis without saving
    """
    try:
        # Check file type
        if not is_allowed_file(file.filename):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
            )

        # Get file extension
        file_extension = os.path.splitext(file.filename)[1]
        
        # Read file content
        content = await file.read()
        
        try:
            # Analyze resume
            result = await process_resume(content, file_extension)
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing resume: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Failed to analyze resume"
            )
            
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error processing file: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Error processing file"
        )

@router.delete("/{resume_id}", status_code=status.HTTP_200_OK)
async def delete_resume(
    resume_id: str,
    current_user: User = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Delete resume by ID
    
    Args:
        resume_id: Resume ID to delete
        current_user: Current user
        db: Database connection
        
    Returns:
        Status 200 OK on successful deletion
    """
    try:
        # Check ObjectId validity
        try:
            object_id = ObjectId(resume_id)
        except:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid resume ID format"
            )
        
        # Check that resume exists and belongs to current user
        resume = await db.resumes.find_one({
            "_id": object_id,
            "user_id": str(current_user.id)
        })
        
        if not resume:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resume not found or access denied"
            )
        
        # If we have a file, also delete it from GridFS
        if "file_id" in resume:
            fs = AsyncIOMotorGridFSBucket(db)
            try:
                await fs.delete(ObjectId(resume["file_id"]))
                logger.info(f"Resume file deleted from GridFS: {resume['file_id']}")
            except Exception as e:
                logger.warning(f"Failed to delete resume file from GridFS: {str(e)}")
        
        # Delete resume from database
        result = await db.resumes.delete_one({"_id": object_id})
        
        if result.deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resume not deleted"
            )
        
        logger.info(f"Resume successfully deleted: {resume_id}")
        return {"message": "Resume successfully deleted", "id": resume_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting resume: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting resume: {str(e)}"
        )

@router.patch("/{resume_id}/status", status_code=status.HTTP_200_OK)
async def update_resume_status(
    resume_id: str,
    status_update: ResumeStatusUpdate,
    current_user: User = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Update resume status
    
    Args:
        resume_id: Resume ID
        status_update: New status
        current_user: Current user
        db: Database connection
        
    Returns:
        Updated resume
    """
    try:
        # Check ObjectId validity
        try:
            object_id = ObjectId(resume_id)
        except:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid resume ID format"
            )
        
        # Check that resume exists and belongs to current user
        resume = await db.resumes.find_one({
            "_id": object_id,
            "user_id": str(current_user.id)
        })
        
        if not resume:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resume not found or access denied"
            )
        
        # Update status
        result = await db.resumes.update_one(
            {"_id": object_id},
            {"$set": {"status": status_update.status}}
        )
        
        if result.modified_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resume not updated"
            )
        
        # Get updated resume
        updated_resume = await db.resumes.find_one({"_id": object_id})
        # Используем _id вместо id для правильной работы с моделью Pydantic
        updated_resume["_id"] = str(updated_resume["_id"])
        
        return Resume(**updated_resume)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating resume status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating resume status: {str(e)}"
        )

@router.post("/scoring", response_model=Resume)
async def score_resume(
    request: ResumeScoringRequest,
    current_user: User = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Analyze and score a resume based on multiple criteria.
    
    Args:
        request: Request containing resume ID
        current_user: Current authenticated user
        db: Database connection
        
    Returns:
        Resume with scoring analysis
    """
    try:
        # Validate ObjectId
        try:
            object_id = ObjectId(request.resume_id)
        except:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid resume ID format"
            )
        
        # Get resume from database
        resume = await db.resumes.find_one({
            "_id": object_id,
            "user_id": str(current_user.id)
        })
        
        if not resume:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resume not found or access denied"
            )
        
        # Get candidate data from resume
        candidate_data = resume.get('candidate', {})
        if not candidate_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No candidate data found in resume"
            )
        
        # Analyze resume using Claude
        claude_client = ClaudeClient()
        scoring_result = await claude_client.analyze_resume(candidate_data)
        
        # Update resume with scoring results in MongoDB
        update_result = await db.resumes.update_one(
            {"_id": object_id},
            {
                "$set": {
                    "scoring": scoring_result.get("scoring", {}),
                    "feedback": scoring_result.get("feedback", {}),
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        if update_result.modified_count == 0:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update resume with scoring results"
            )
        
        # Get updated resume
        updated_resume = await db.resumes.find_one({"_id": object_id})
        
        # Convert ObjectId to string for response
        updated_resume['_id'] = str(updated_resume['_id'])
        
        return Resume(**updated_resume)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error scoring resume: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error scoring resume: {str(e)}"
        ) 