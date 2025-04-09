from fastapi import APIRouter, Depends, HTTPException, status
from models.job_queries import JobQueryGenerateRequest, JobQueryResponse
from models.users import User
from core.auth import get_current_user
from core.claude_client import ClaudeClient
from bson import ObjectId
from core.database import get_db

router = APIRouter(tags=["job-queries"])

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