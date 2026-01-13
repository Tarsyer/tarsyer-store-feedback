"""
Core configuration for Store Feedback System
"""
from pydantic_settings import BaseSettings
from functools import lru_cache
from pathlib import Path
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Application
    APP_NAME: str = "Store Feedback System"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # MongoDB
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "store_feedback"
    
    # JWT Authentication
    JWT_SECRET_KEY: str = "your-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    
    # File Storage
    UPLOAD_DIR: str = "/var/data/store-feedback/uploads"
    MAX_FILE_SIZE_MB: int = 50
    ALLOWED_EXTENSIONS: set = {".mp3", ".mp4", ".m4a", ".wav", ".webm", ".ogg", ".flac", ".aac", ".mpeg", ".mpga"}
    
    # Whisper Transcription
    WHISPER_CLI_PATH: str = os.path.expanduser("~/whisper.cpp/build/bin/whisper-cli")
    WHISPER_MODEL_PATH: str = os.path.expanduser("~/whisper.cpp/models/ggml-medium.bin")
    WHISPER_LANGUAGE: str = "hi"  # Hindi
    
    # Qwen3 LLM API
    QWEN_API_URL: str = "https://kwen.tarsyer.com/v1/chat/completions"
    QWEN_API_KEY: str = "Tarsyer-key-1"
    QWEN_TARGET_SERVER: str = "BK"
    QWEN_MAX_TOKENS: int = 1000
    
    # Background Processing
    PROCESS_INTERVAL_SECONDS: int = 30
    MAX_CONCURRENT_TRANSCRIPTIONS: int = 2
    
    # CORS
    CORS_ORIGINS: list = ["http://localhost:3000", "http://localhost:5173", "https://store-feedback.tarsyer.com"]
    
    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance"""
    return Settings()


# Ensure upload directory exists
def init_directories():
    settings = get_settings()
    Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
