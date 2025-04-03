from fastapi import APIRouter, Depends, Response, status
from services.health import HealthService
from api.deps import get_health_service
import logging
import json

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get(
    "/health",
    summary="System health check",
    description="Performs a comprehensive health check of all system components",
    response_description="Health status of the system and its components",
    status_code=status.HTTP_200_OK,
    responses={
        503: {"description": "Service unavailable"},
    }
)
async def health_check(
    health_service: HealthService = Depends(get_health_service)
):
    """
    Comprehensive system health check endpoint.
    Verifies the health of all critical system components.
    """
    response = await health_service.check_health()
    
    # Set appropriate status code based on health status
    if response['status'] != 'healthy':
        return Response(
            content=json.dumps(response),
            media_type="application/json",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE
        )
    
    return response 