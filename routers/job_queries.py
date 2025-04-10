from fastapi import APIRouter, Depends, HTTPException, status
from models.job_queries import (
    JobQueryGenerateRequest, 
    JobQueryResponse,
    JobQueryCreate,
    JobQueryUpdate,
    JobQueryStatusUpdate,
    JobQuery,
)
from models.users import User
from core.auth import get_current_user
from core.claude_client import ClaudeClient
from bson import ObjectId
from core.database import get_db
from typing import List
from datetime import datetime

router = APIRouter(tags=["job-queries"])

@router.get("/list", response_model=List[JobQuery])
async def list_job_queries(
    current_user: User = Depends(get_current_user)
):
    """Get list of user's job queries"""
    try:
        db = get_db()
        queries = await db.job_queries.find(
            {"user_id": str(current_user.id)}
        ).to_list(length=None)
        return [JobQuery(**{**query, "id": str(query.pop("_id"))}) for query in queries]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/", response_model=JobQuery, status_code=status.HTTP_201_CREATED)
async def create_job_query(
    query: JobQueryCreate,
    current_user: User = Depends(get_current_user)
):
    """Create new job query"""
    try:
        db = get_db()
        query_data = query.model_dump()
        query_data["user_id"] = str(current_user.id)
        query_data["created_at"] = query_data["updated_at"] = datetime.utcnow()
        
        result = await db.job_queries.insert_one(query_data)
        query_data["id"] = str(result.inserted_id)
        
        return JobQuery(**query_data)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/{query_id}", response_model=JobQuery)
async def get_job_query(
    query_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get job query by ID"""
    try:
        db = get_db()
        query = await db.job_queries.find_one({
            "_id": ObjectId(query_id),
            "user_id": str(current_user.id)
        })
        
        if not query:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job query not found"
            )
            
        return JobQuery(**{**query, "id": str(query.pop("_id"))})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.patch("/{query_id}", response_model=JobQuery)
async def update_job_query(
    query_id: str,
    query_update: JobQueryUpdate,
    current_user: User = Depends(get_current_user)
):
    """Update job query"""
    try:
        db = get_db()
        update_data = query_update.model_dump(exclude_unset=True)
        update_data["updated_at"] = datetime.utcnow()
        
        result = await db.job_queries.update_one(
            {
                "_id": ObjectId(query_id),
                "user_id": str(current_user.id)
            },
            {"$set": update_data}
        )
        
        if result.matched_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job query not found"
            )
            
        updated_query = await db.job_queries.find_one({
            "_id": ObjectId(query_id)
        })
        return JobQuery(**{**updated_query, "id": str(updated_query.pop("_id"))})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.patch("/{query_id}/status", response_model=JobQuery)
async def update_job_query_status(
    query_id: str,
    status_update: JobQueryStatusUpdate,
    current_user: User = Depends(get_current_user)
):
    """Update job query status"""
    try:
        db = get_db()
        result = await db.job_queries.update_one(
            {
                "_id": ObjectId(query_id),
                "user_id": str(current_user.id)
            },
            {
                "$set": {
                    "status": status_update.status,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        if result.matched_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job query not found"
            )
            
        updated_query = await db.job_queries.find_one({
            "_id": ObjectId(query_id)
        })
        return JobQuery(**{**updated_query, "id": str(updated_query.pop("_id"))})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/generate", response_model=JobQueryResponse)
async def generate_job_query(
    request: JobQueryGenerateRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Generate job query keywords based on resume data
    
    Args:
        request: Request with resume_id
        current_user: Current user
        
    Returns:
        Generated keywords for job search
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
        
        # Extract candidate data from resume, excluding service fields
        candidate_data = {
            k: v for k, v in resume.items() 
            if k not in ["_id", "user_id", "filename", "file_id", "status", "created_at", "updated_at"]
        }
        
        # Generate keywords using Claude
        keywords = await claude_client.generate_job_query_keywords(
            candidate_data=candidate_data
        )
        
        return JobQueryResponse(keywords=keywords)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        ) 