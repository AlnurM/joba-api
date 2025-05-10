from fastapi import APIRouter, HTTPException, Depends, status
from models import User, UserCreate
from models.auth import SignInRequest, AccessToken, AvailabilityCheck, AvailabilityResponse
from core.auth import (
    create_access_token,
    create_refresh_token, authenticate_user, get_current_user,
    refresh_access_token, ACCESS_TOKEN_EXPIRE_HOURS,
    check_availability, create_user
)
import logging
from datetime import timedelta
from pydantic import BaseModel
from core.database import get_db
from bson import ObjectId

router = APIRouter(tags=["authentication"])
logger = logging.getLogger(__name__)

@router.post("/signup", response_model=AccessToken)
async def signup(user: UserCreate):
    """
    Register a new user.
    Only email and password are required, username is optional.
    Returns access and refresh tokens upon successful registration.
    """
    try:
        created_user = await create_user(user)
        access_token_expires = timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
        access_token = create_access_token(
            data={"sub": str(created_user.id)}, expires_delta=access_token_expires
        )
        refresh_token = create_refresh_token(data={"sub": str(created_user.id)})
        return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}
    except HTTPException as e:
        # Propagate HTTPException
        raise e
    except Exception as e:
        logger.error(f"Error during signup: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error during signup"
        )

@router.post("/signin", response_model=AccessToken)
async def signin(user_data: SignInRequest):
    """
    User login.
    Can use either email or username for login.
    """
    try:
        logger.info(f"Attempting to authenticate user with login: {user_data.login}")
        user = await authenticate_user(user_data.login, user_data.password)
        
        logger.info(f"User authenticated successfully: {user.email}")
        access_token_expires = timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
        access_token = create_access_token(
            data={"sub": str(user.id)}, expires_delta=access_token_expires
        )
        refresh_token = create_refresh_token(data={"sub": str(user.id)})
        return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}
    except HTTPException as e:
        # Propagate HTTPException
        raise e
    except Exception as e:
        logger.error(f"Error during signin: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error during signin"
        )

@router.post("/refresh", response_model=AccessToken)
async def refresh_token(refresh_token: str):
    """
    Refresh access token using refresh token
    """
    try:
        access_token = await refresh_access_token(refresh_token)
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }
    except HTTPException as e:
        # Propagate HTTPException
        raise e
    except Exception as e:
        logger.error(f"Error during token refresh: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error during token refresh"
        )

@router.get("/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """
    Get current user information
    """
    return current_user

@router.post("/check-availability", response_model=AvailabilityResponse)
async def check_username_email_availability(check_data: AvailabilityCheck):
    """
    Check email and username availability.
    Can check both fields simultaneously or separately.
    """
    try:
        result = await check_availability(
            email=check_data.email,
            username=check_data.username
        )
        return AvailabilityResponse(**result)
    except HTTPException as e:
        # Propagate HTTPException
        raise e
    except Exception as e:
        logger.error(f"Error checking availability: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error checking availability"
        )

class OnboardingUpdate(BaseModel):
    """Model for updating onboarding status"""
    onboarding: bool

@router.patch("/onboarding", response_model=User)
async def update_onboarding(
    update_data: OnboardingUpdate,
    current_user: User = Depends(get_current_user)
):
    """
    Update user's onboarding status
    """
    try:
        db = get_db()
        await db.users.update_one(
            {"_id": ObjectId(current_user.id)},
            {"$set": {"onboarding": update_data.onboarding}}
        )
            
        updated_user = await db.users.find_one({"_id": ObjectId(current_user.id)})
        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
            
        updated_user["id"] = str(updated_user["_id"])
        del updated_user["_id"]
        
        return User(**updated_user)
    except Exception as e:
        logger.error(f"Error updating onboarding status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating onboarding status"
        ) 