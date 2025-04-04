from fastapi import APIRouter, HTTPException, Depends, status
from models import User, UserCreate, UserLogin, Token, AvailabilityCheck, AvailabilityResponse
from core.auth import (
    get_password_hash, verify_password, create_access_token,
    create_refresh_token, authenticate_user, get_current_user,
    refresh_access_token, ACCESS_TOKEN_EXPIRE_HOURS,
    check_availability, create_user
)
import logging
from datetime import timedelta

router = APIRouter(prefix="/auth", tags=["authentication"])
logger = logging.getLogger(__name__)

@router.post("/signup", response_model=User)
async def signup(user: UserCreate):
    """
    Регистрация нового пользователя.
    Требуется только email и пароль, username опционален.
    """
    try:
        return await create_user(user)
    except HTTPException as e:
        # Пробрасываем HTTPException дальше
        raise e
    except Exception as e:
        logger.error(f"Error during signup: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error during signup"
        )

@router.post("/signin", response_model=Token)
async def signin(user_data: UserLogin):
    """
    Вход в систему.
    Можно использовать email или username для входа.
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
        # Пробрасываем HTTPException дальше
        raise e
    except Exception as e:
        logger.error(f"Error during signin: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error during signin"
        )

@router.post("/refresh", response_model=Token)
async def refresh_token(refresh_token: str):
    """
    Обновление access token с помощью refresh token
    """
    try:
        access_token = await refresh_access_token(refresh_token)
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }
    except HTTPException as e:
        # Пробрасываем HTTPException дальше
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
    Получение информации о текущем пользователе
    """
    return current_user

@router.post("/check-availability", response_model=AvailabilityResponse)
async def check_username_email_availability(check_data: AvailabilityCheck):
    """
    Проверка доступности email и username.
    Можно проверить оба поля одновременно или по отдельности.
    """
    try:
        result = await check_availability(
            email=check_data.email,
            username=check_data.username
        )
        return AvailabilityResponse(**result)
    except HTTPException as e:
        # Пробрасываем HTTPException дальше
        raise e
    except Exception as e:
        logger.error(f"Error checking availability: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error checking availability"
        ) 