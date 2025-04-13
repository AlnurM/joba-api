from fastapi import APIRouter, Depends, HTTPException, status
from models.job_queries import (
    JobQueryGenerateRequest, 
    JobQueryResponse,
    JobQueryCreate,
    JobQueryUpdate,
    JobQueryStatusUpdate,
    JobQuery,
    JobQueryStatus
)
from models.users import User
from core.auth import get_current_user
from core.claude_client import ClaudeClient
from bson import ObjectId
from core.database import get_db
from typing import Dict, Any, Optional
from datetime import datetime

router = APIRouter(tags=["job-queries"])

async def get_job_queries_by_user(
    user_id: str,
    page: int = 1,
    per_page: int = 10,
    status: Optional[JobQueryStatus] = None
) -> Dict[str, Any]:
    """
    Get user's job queries with pagination
    
    Args:
        user_id: User ID
        page: Page number (1-based)
        per_page: Number of items per page
        status: Optional job query status filter
        
    Returns:
        Dictionary with list of queries and pagination info
    """
    skip = (page - 1) * per_page
    db = get_db()
    
    # Form search conditions
    query = {"user_id": user_id}
    if status is not None:
        query["status"] = status
    
    # Get total number of documents
    total = await db.job_queries.count_documents(query)
    
    # Get documents with pagination
    cursor = db.job_queries.find(query).sort([
        ("status", 1),  # 1 for ascending, to have "active" first
        ("created_at", -1)  # -1 for descending, to have newest first
    ]).skip(skip).limit(per_page)
    queries = await cursor.to_list(length=per_page)
    
    # Convert ObjectId to strings
    processed_queries = []
    for query in queries:
        query_dict = {
            "id": str(query["_id"]),
            "user_id": query["user_id"],
            "name": query["name"],
            "keywords": query["keywords"],
            "query": query["query"],
            "status": query.get("status", JobQueryStatus.ARCHIVED),
            "created_at": query.get("created_at", datetime.utcnow()),
            "updated_at": query.get("updated_at", datetime.utcnow())
        }
        processed_queries.append(query_dict)
    
    return {
        "list": processed_queries,
        "pagination": {
            "total": total,
            "currentPage": page,
            "totalPages": (total + per_page - 1) // per_page,
            "perPage": per_page
        }
    }

@router.get("/list", response_model=Dict[str, Any])
async def list_job_queries(
    page: int = 1,
    per_page: int = 10,
    status: Optional[JobQueryStatus] = None,
    current_user: User = Depends(get_current_user)
):
    """
    Get list of user's job queries with pagination
    
    Args:
        page: Page number (1-based)
        per_page: Number of items per page
        status: Optional job query status filter
        current_user: Current authenticated user
        
    Returns:
        Dictionary with list of queries and pagination info
    """
    try:
        return await get_job_queries_by_user(
            user_id=str(current_user.id),
            page=page,
            per_page=per_page,
            status=status
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("", response_model=JobQuery, status_code=status.HTTP_201_CREATED)
async def create_job_query(
    query: JobQueryCreate,
    current_user: User = Depends(get_current_user)
):
    """
    Create new job query
    
    Args:
        query: Job query data
        current_user: Current authenticated user
        
    Returns:
        Created job query
    """
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
    """
    Get job query by ID
    
    Args:
        query_id: Job query ID
        current_user: Current authenticated user
        
    Returns:
        Job query data
    """
    try:
        db = get_db()
        
        # Check ObjectId validity
        try:
            object_id = ObjectId(query_id)
        except:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid job query ID format"
            )
        
        query = await db.job_queries.find_one({
            "_id": object_id,
            "user_id": str(current_user.id)
        })
        
        if not query:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job query not found or access denied"
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
    """
    Update job query
    
    Args:
        query_id: Job query ID
        query_update: Update data
        current_user: Current authenticated user
        
    Returns:
        Updated job query
    """
    try:
        db = get_db()
        
        # Check ObjectId validity
        try:
            object_id = ObjectId(query_id)
        except:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid job query ID format"
            )
        
        update_data = query_update.model_dump(exclude_unset=True)
        update_data["updated_at"] = datetime.utcnow()
        
        result = await db.job_queries.update_one(
            {
                "_id": object_id,
                "user_id": str(current_user.id)
            },
            {"$set": update_data}
        )
        
        if result.matched_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job query not found or access denied"
            )
            
        updated_query = await db.job_queries.find_one({
            "_id": object_id
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
    """
    Update job query status
    
    Args:
        query_id: Job query ID
        status_update: New status
        current_user: Current authenticated user
        
    Returns:
        Updated job query
    """
    try:
        db = get_db()
        
        # Check ObjectId validity
        try:
            object_id = ObjectId(query_id)
        except:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid job query ID format"
            )
        
        result = await db.job_queries.update_one(
            {
                "_id": object_id,
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
                detail="Job query not found or access denied"
            )
            
        updated_query = await db.job_queries.find_one({
            "_id": object_id
        })
        return JobQuery(**{**updated_query, "id": str(updated_query.pop("_id"))})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.delete("/{query_id}", status_code=status.HTTP_200_OK)
async def delete_job_query(
    query_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Delete job query
    
    Args:
        query_id: Job query ID
        current_user: Current authenticated user
        
    Returns:
        Success message
    """
    try:
        db = get_db()
        
        # Check ObjectId validity
        try:
            object_id = ObjectId(query_id)
        except:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid job query ID format"
            )
        
        result = await db.job_queries.delete_one({
            "_id": object_id,
            "user_id": str(current_user.id)
        })
        
        if result.deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job query not found or access denied"
            )
            
        return {"message": "Job query deleted successfully"}
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