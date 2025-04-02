from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from core.config import get_settings
from core.exceptions import AuthenticationError
from services.auth import AuthService
from domain.models import User, UserCreate, Token
import logging

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/signin")
settings = get_settings()
logger = logging.getLogger(__name__)

def get_auth_service() -> AuthService:
    """Dependency to get AuthService instance"""
    return AuthService()

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    auth_service: AuthService = Depends(get_auth_service)
) -> User:
    """Dependency to get current user from token"""
    return await auth_service.get_current_user(token)

@router.post("/signup", response_model=User)
async def signup(
    user: UserCreate,
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Register a new user.
    Only email and password are required, username is optional.
    """
    try:
        return await auth_service.create_user(user)
    except AuthenticationError as e:
        logger.error(f"Error during signup: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.post("/signin", response_model=Token)
async def signin(
    form_data: OAuth2PasswordRequestForm = Depends(),
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Sign in to the system.
    Can use either email or username for login.
    """
    try:
        logger.info(f"Attempting to authenticate user with login: {form_data.username}")
        user = await auth_service.authenticate_user(form_data.username, form_data.password)
        if not user:
            logger.warning(f"Authentication failed for login: {form_data.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect login or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        logger.info(f"User authenticated successfully: {user.email}")
        access_token_expires = timedelta(hours=settings.ACCESS_TOKEN_EXPIRE_HOURS)
        access_token = auth_service.create_access_token(
            data={"sub": str(user.id)},
            expires_delta=access_token_expires
        )
        refresh_token = auth_service.create_refresh_token(
            data={"sub": str(user.id)}
        )
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }
    except Exception as e:
        logger.error(f"Error during signin: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.post("/refresh", response_model=Token)
async def refresh_token(
    refresh_token: str,
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Refresh access token using refresh token
    """
    try:
        access_token = await auth_service.refresh_access_token(refresh_token)
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }
    except AuthenticationError as e:
        logger.error(f"Error during token refresh: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

@router.get("/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """
    Get current user information
    """
    return current_user

@router.post("/check-availability")
async def check_username_email_availability(
    email: str | None = None,
    username: str | None = None,
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Check availability of email and username.
    Can check both fields simultaneously or separately.
    """
    try:
        available, message = await auth_service.check_availability(email, username)
        return {"available": available, "message": message}
    except Exception as e:
        logger.error(f"Error checking availability: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        ) 