"""
MongoDB database service
"""
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from typing import Optional
import logging

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class Database:
    """MongoDB connection manager"""
    
    client: Optional[AsyncIOMotorClient] = None
    db: Optional[AsyncIOMotorDatabase] = None
    
    @classmethod
    async def connect(cls):
        """Connect to MongoDB"""
        settings = get_settings()
        try:
            cls.client = AsyncIOMotorClient(settings.MONGODB_URL)
            cls.db = cls.client[settings.MONGODB_DB_NAME]
            
            # Verify connection
            await cls.client.admin.command('ping')
            logger.info(f"Connected to MongoDB: {settings.MONGODB_DB_NAME}")
            
            # Create indexes
            await cls._create_indexes()
            
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise
    
    @classmethod
    async def disconnect(cls):
        """Disconnect from MongoDB"""
        if cls.client:
            cls.client.close()
            logger.info("Disconnected from MongoDB")
    
    @classmethod
    async def _create_indexes(cls):
        """Create necessary indexes for performance"""
        if cls.db is None:
            return
        
        # Feedbacks collection indexes
        await cls.db.feedbacks.create_index([("store_id", 1), ("feedback_date", -1)])
        await cls.db.feedbacks.create_index([("feedback_date", -1)])
        await cls.db.feedbacks.create_index([("transcription_status", 1)])
        await cls.db.feedbacks.create_index([("analysis_status", 1)])
        await cls.db.feedbacks.create_index([("submitted_at", -1)])
        
        # Stores collection indexes
        await cls.db.stores.create_index([("store_id", 1)], unique=True)
        
        # Users collection indexes
        await cls.db.users.create_index([("username", 1)], unique=True)
        
        # Daily analytics indexes
        await cls.db.daily_analytics.create_index([("date", -1), ("store_id", 1)], unique=True)
        
        logger.info("Database indexes created/verified")
    
    @classmethod
    def get_db(cls) -> AsyncIOMotorDatabase:
        """Get database instance"""
        if cls.db is None:
            raise RuntimeError("Database not connected. Call Database.connect() first.")
        return cls.db


# Dependency for FastAPI
async def get_database() -> AsyncIOMotorDatabase:
    """FastAPI dependency to get database"""
    return Database.get_db()
