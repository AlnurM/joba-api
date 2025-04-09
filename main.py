"""Main application module"""

import logging
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from core.database import init_db
from routers import auth, resumes, cover_letters, default, job_queries

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Get port from environment variables (for Railway)
PORT = int(os.getenv("PORT", 8000))

# Authentication scheme
app = FastAPI(
    title="Joba API",
    description="API for job application management",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database
@app.on_event("startup")
async def startup_event():
    try:
        await init_db()
        logger.info("Successfully connected to MongoDB")
        logger.info(f"Application will run on port: {PORT}")
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {str(e)}")
        raise

# Include routers
app.include_router(default.router, tags=["default"])
app.include_router(auth.router, prefix="/auth", tags=["authentication"])
app.include_router(resumes.router, prefix="/resumes", tags=["resumes"])
app.include_router(cover_letters.router, prefix="/cover-letters", tags=["cover-letters"])
app.include_router(job_queries.router, prefix="/job-queries", tags=["job-queries"]) 