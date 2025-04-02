from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from services.auth import AuthService
from services.resume import ResumeService
from domain.models import User

security = HTTPBearer()

def get_auth_service() -> AuthService:
    return AuthService()

def get_resume_service() -> ResumeService:
    return ResumeService()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    auth_service: AuthService = Depends(get_auth_service)
) -> User:
    try:
        return await auth_service.get_current_user(credentials.credentials)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        ) 