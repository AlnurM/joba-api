from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status, Response
from typing import List
from services.resume import ResumeService
from domain.models import Resume, User
from api.deps import get_current_user, get_resume_service

router = APIRouter()

@router.post("/upload", response_model=Resume)
async def upload_resume(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    resume_service: ResumeService = Depends(get_resume_service)
):
    try:
        return await resume_service.create(file, str(current_user.id))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/list", response_model=List[Resume])
async def list_resumes(
    skip: int = 0,
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    resume_service: ResumeService = Depends(get_resume_service)
):
    return await resume_service.get_user_resumes(str(current_user.id), skip, limit)

@router.get("/{resume_id}/download")
async def download_resume(
    resume_id: str,
    current_user: User = Depends(get_current_user),
    resume_service: ResumeService = Depends(get_resume_service)
):
    try:
        file_content, filename = await resume_service.get_resume_file(
            resume_id, str(current_user.id)
        )
        return Response(
            content=file_content,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )

@router.patch("/{resume_id}/status", response_model=Resume)
async def update_resume_status(
    resume_id: str,
    status: str,
    current_user: User = Depends(get_current_user),
    resume_service: ResumeService = Depends(get_resume_service)
):
    try:
        return await resume_service.update_status(resume_id, str(current_user.id), status)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.delete("/{resume_id}")
async def delete_resume(
    resume_id: str,
    current_user: User = Depends(get_current_user),
    resume_service: ResumeService = Depends(get_resume_service)
):
    try:
        await resume_service.delete(resume_id, str(current_user.id))
        return {"message": "Resume deleted successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        ) 