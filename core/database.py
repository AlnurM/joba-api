from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging

# Logging setup
logger = logging.getLogger(__name__)

# Global variables for client and database
client = None
db = None

def get_db():
    """Get database instance"""
    if db is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return db

async def init_db():
    """Initialize database connection"""
    global client, db
    
    try:
        # Get database URL
        mongo_url = os.getenv("MONGO_URL")
        if not mongo_url:
            raise ValueError("MONGO_URL environment variable is not set")
        
        logger.info(f"Attempting to connect to MongoDB with URL: {mongo_url}")
        
        # Create client and connect to database
        client = AsyncIOMotorClient(mongo_url)
        await client.admin.command('ping')
        logger.info("Successfully pinged MongoDB server")
        
        # Initialize database
        db = client.joba
        logger.info("Successfully initialized database connection")
        
        # Check users collection access
        await db.users.find_one()
        logger.info("Successfully accessed users collection")
    except Exception as e:
        logger.error(f"Failed to initialize database: {str(e)}")
        raise 