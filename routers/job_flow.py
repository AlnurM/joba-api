from fastapi import APIRouter, Depends, HTTPException, status
from models.job_flow import (
    JobFlowCreate,
    JobFlowUpdate,
    JobFlowStatusUpdate,
    JobFlow,
    JobFlowStatus
)
from models.users import User
from core.auth import get_current_user
from bson import ObjectId
from core.database import get_db
from typing import Dict, Any, Optional, List
from datetime import datetime

router = APIRouter(tags=["job-flow"])

async def get_job_flows_by_user(
    user_id: str,
    page: int = 1,
    per_page: int = 10,
    status: Optional[JobFlowStatus] = None
) -> Dict[str, Any]:
    """
    Get user's job flows with pagination
    
    Args:
        user_id: User ID
        page: Page number (1-based)
        per_page: Number of items per page
        status: Optional job flow status filter
        
    Returns:
        Dictionary with list of job flows and pagination info
    """
    skip = (page - 1) * per_page
    db = get_db()
    
    # Form match conditions
    match_stage = {"user_id": user_id}
    if status is not None:
        match_stage["status"] = status
    
    # Get total number of documents
    total = await db.job_flows.count_documents(match_stage)
    
    # Create aggregation pipeline
    pipeline = [
        # Match the job flows for this user
        {"$match": match_stage},
        # Sort by status (active first) then by date (newest first)
        {"$sort": {"status": 1, "created_at": -1}},
        # Apply pagination
        {"$skip": skip},
        {"$limit": per_page},
        # Lookup resume data
        {"$lookup": {
            "from": "resumes",
            "let": {"resume_id": {"$toObjectId": "$resume_id"}},
            "pipeline": [
                {"$match": {"$expr": {"$eq": ["$_id", "$$resume_id"]}}},
                {"$project": {"_id": 1, "filename": 1}}
            ],
            "as": "resume_data"
        }},
        # Lookup cover letter data
        {"$lookup": {
            "from": "cover_letters",
            "let": {"cover_letter_id": {"$toObjectId": "$cover_letter_id"}},
            "pipeline": [
                {"$match": {"$expr": {"$eq": ["$_id", "$$cover_letter_id"]}}},
                {"$project": {"_id": 1, "name": 1, "content": 1}}
            ],
            "as": "cover_letter_data"
        }},
        # Lookup job query data
        {"$lookup": {
            "from": "job_queries",
            "let": {"job_query_id": {"$toObjectId": "$job_query_id"}},
            "pipeline": [
                {"$match": {"$expr": {"$eq": ["$_id", "$$job_query_id"]}}},
                {"$project": {"_id": 1, "name": 1, "query": 1}}
            ],
            "as": "job_query_data"
        }},
        # Structure the output
        {"$project": {
            "_id": 1,
            "user_id": 1,
            "source": 1,
            "status": 1,
            "created_at": 1,
            "updated_at": 1,
            "resume": {
                "$cond": {
                    "if": {"$gt": [{"$size": "$resume_data"}, 0]},
                    "then": {
                        "id": {"$toString": {"$arrayElemAt": ["$resume_data._id", 0]}},
                        "filename": {"$arrayElemAt": ["$resume_data.filename", 0]}
                    },
                    "else": {
                        "id": "$resume_id",
                        "filename": ""
                    }
                }
            },
            "cover_letter": {
                "$cond": {
                    "if": {"$gt": [{"$size": "$cover_letter_data"}, 0]},
                    "then": {
                        "id": {"$toString": {"$arrayElemAt": ["$cover_letter_data._id", 0]}},
                        "name": {"$arrayElemAt": ["$cover_letter_data.name", 0]},
                        "content": {"$arrayElemAt": ["$cover_letter_data.content", 0]}
                    },
                    "else": {
                        "id": "$cover_letter_id",
                        "name": "",
                        "content": ""
                    }
                }
            },
            "job_query": {
                "$cond": {
                    "if": {"$gt": [{"$size": "$job_query_data"}, 0]},
                    "then": {
                        "id": {"$toString": {"$arrayElemAt": ["$job_query_data._id", 0]}},
                        "name": {"$arrayElemAt": ["$job_query_data.name", 0]},
                        "query": {"$arrayElemAt": ["$job_query_data.query", 0]}
                    },
                    "else": {
                        "id": "$job_query_id",
                        "name": "",
                        "query": ""
                    }
                }
            }
        }}
    ]
    
    # Execute the aggregation pipeline
    cursor = db.job_flows.aggregate(pipeline)
    job_flows = await cursor.to_list(length=per_page)
    
    # Process results to ensure correct field names
    processed_job_flows = []
    for job_flow in job_flows:
        job_flow_dict = {
            "id": str(job_flow["_id"]),
            "user_id": job_flow["user_id"],
            "source": job_flow["source"],
            "status": job_flow["status"],
            "created_at": job_flow["created_at"],
            "updated_at": job_flow["updated_at"],
            "resume": job_flow["resume"],
            "cover_letter": job_flow["cover_letter"],
            "job_query": job_flow["job_query"]
        }
        processed_job_flows.append(job_flow_dict)
    
    return {
        "list": processed_job_flows,
        "pagination": {
            "total": total,
            "currentPage": page,
            "totalPages": (total + per_page - 1) // per_page,
            "perPage": per_page
        }
    }

@router.get("/list", response_model=Dict[str, Any])
async def list_job_flows(
    page: int = 1,
    per_page: int = 10,
    status: Optional[JobFlowStatus] = None,
    current_user: User = Depends(get_current_user)
):
    """
    Get list of user's job flows with pagination
    
    Args:
        page: Page number (1-based)
        per_page: Number of items per page
        status: Optional job flow status filter
        current_user: Current authenticated user
        
    Returns:
        Dictionary with list of job flows and pagination info
    """
    try:
        return await get_job_flows_by_user(
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

@router.post("", response_model=JobFlow, status_code=status.HTTP_201_CREATED)
async def create_job_flow(
    job_flow: JobFlowCreate,
    current_user: User = Depends(get_current_user)
):
    """
    Create new job flow
    
    Args:
        job_flow: Job flow data
        current_user: Current authenticated user
        
    Returns:
        Created job flow
    """
    try:
        db = get_db()
        
        # Check if resume exists and belongs to the user
        resume = await db.resumes.find_one({
            "_id": ObjectId(job_flow.resume_id),
            "user_id": str(current_user.id)
        })
        if not resume:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resume not found or access denied"
            )
        
        # Check if cover letter exists and belongs to the user
        cover_letter = await db.cover_letters.find_one({
            "_id": ObjectId(job_flow.cover_letter_id),
            "user_id": str(current_user.id)
        })
        if not cover_letter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cover letter not found or access denied"
            )
        
        # Check if job query exists and belongs to the user
        job_query = await db.job_queries.find_one({
            "_id": ObjectId(job_flow.job_query_id),
            "user_id": str(current_user.id)
        })
        if not job_query:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job query not found or access denied"
            )
        
        # Create job flow
        job_flow_data = job_flow.model_dump()
        job_flow_data["user_id"] = str(current_user.id)
        job_flow_data["created_at"] = job_flow_data["updated_at"] = datetime.utcnow()
        
        result = await db.job_flows.insert_one(job_flow_data)
        job_flow_data["id"] = str(result.inserted_id)
        
        return JobFlow(**job_flow_data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.delete("/{job_flow_id}", status_code=status.HTTP_200_OK)
async def delete_job_flow(
    job_flow_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Delete job flow
    
    Args:
        job_flow_id: Job flow ID
        current_user: Current authenticated user
        
    Returns:
        Success message
    """
    try:
        db = get_db()
        
        # Check ObjectId validity
        try:
            object_id = ObjectId(job_flow_id)
        except:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid job flow ID format"
            )
        
        # Check if job flow exists and belongs to the user
        job_flow = await db.job_flows.find_one({
            "_id": object_id,
            "user_id": str(current_user.id)
        })
        
        if not job_flow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job flow not found or access denied"
            )
        
        # Delete job flow
        result = await db.job_flows.delete_one({
            "_id": object_id,
            "user_id": str(current_user.id)
        })
        
        if result.deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete job flow"
            )
        
        return {"message": "Job flow successfully deleted", "id": job_flow_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.patch("/{job_flow_id}/status", response_model=JobFlow)
async def update_job_flow_status(
    job_flow_id: str,
    status_update: JobFlowStatusUpdate,
    current_user: User = Depends(get_current_user)
):
    """
    Update job flow status
    
    Args:
        job_flow_id: Job flow ID
        status_update: New status
        current_user: Current authenticated user
        
    Returns:
        Updated job flow
    """
    try:
        db = get_db()
        
        # Check ObjectId validity
        try:
            object_id = ObjectId(job_flow_id)
        except:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid job flow ID format"
            )
        
        # Check if job flow exists and belongs to the user
        job_flow = await db.job_flows.find_one({
            "_id": object_id,
            "user_id": str(current_user.id)
        })
        
        if not job_flow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job flow not found or access denied"
            )
        
        # Update status
        result = await db.job_flows.update_one(
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
                detail="Job flow not updated"
            )
        
        # Get updated job flow
        updated_job_flow = await db.job_flows.find_one({"_id": object_id})
        updated_job_flow["id"] = str(updated_job_flow.pop("_id"))
        
        return JobFlow(**updated_job_flow)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        ) 