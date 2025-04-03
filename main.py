from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.database import init_db
import logging
from api.endpoints import auth, resumes, health, cover_letters

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Joba API",
    description="API for managing resumes and job applications",
    version="1.0.0",
    openapi_tags=[
        {
            "name": "Authentication",
            "description": "User authentication and account management operations"
        },
        {
            "name": "Resumes",
            "description": "Resume management operations"
        },
        {
            "name": "Health",
            "description": "System health monitoring endpoints"
        },
        {
            "name": "Cover Letters",
            "description": "Cover letter management operations"
        }
    ]
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    """Initialize database and other startup tasks"""
    try:
        await init_db()
        logger.info("Successfully connected to MongoDB")
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {str(e)}")
        raise

# Include routers
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(resumes.router, prefix="/resumes", tags=["Resumes"])
app.include_router(health.router, tags=["Health"])
app.include_router(cover_letters.router, prefix="/cover-letters", tags=["Cover Letters"])

@app.get("/", tags=["Root"])
async def root():
    return {"message": "Welcome to Joba API"} 