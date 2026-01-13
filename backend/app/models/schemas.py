"""
Pydantic models for MongoDB collections and API schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime, date
from enum import Enum
from bson import ObjectId


# Custom ObjectId type for Pydantic
class PyObjectId(str):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v, info):
        if isinstance(v, ObjectId):
            return str(v)
        if isinstance(v, str) and ObjectId.is_valid(v):
            return v
        raise ValueError("Invalid ObjectId")


# Enums
class ToneType(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class ProcessingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class UserRole(str, Enum):
    STAFF = "staff"
    MANAGER = "manager"
    ADMIN = "admin"


# ============ Store Models ============

class StoreBase(BaseModel):
    store_id: str = Field(..., pattern=r'^W\d{3}$', description="Store ID in WXXX format")
    store_name: str
    region: Optional[str] = None
    zone: Optional[str] = None
    active: bool = True


class StoreCreate(StoreBase):
    pass


class Store(StoreBase):
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    
    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}


# ============ User Models ============

class UserBase(BaseModel):
    username: str
    name: str
    role: UserRole = UserRole.STAFF
    store_ids: List[str] = []  # Stores this user has access to


class UserCreate(UserBase):
    password: str


class User(UserBase):
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}


class UserInDB(User):
    password_hash: str


# ============ Feedback Analysis Models ============

class FeedbackAnalysis(BaseModel):
    """LLM analysis output structure"""
    summary: str = ""
    tone: ToneType = ToneType.NEUTRAL
    tone_score: float = Field(default=0.5, ge=0, le=1)
    products: List[str] = []
    issues: List[str] = []
    actions: List[str] = []
    keywords: List[str] = []


# ============ Feedback Models ============

class FeedbackBase(BaseModel):
    store_id: str = Field(..., pattern=r'^W\d{3}$')
    feedback_date: date
    notes: Optional[str] = None


class FeedbackCreate(FeedbackBase):
    """Schema for creating a new feedback (from upload)"""
    pass


class Feedback(FeedbackBase):
    """Full feedback document schema"""
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    store_name: Optional[str] = None
    
    # Submission info
    submitted_at: datetime = Field(default_factory=datetime.utcnow)
    submitted_by: Optional[str] = None
    
    # Audio file info
    audio_url: str = ""
    audio_filename: str = ""
    audio_duration_seconds: Optional[float] = None
    file_size_bytes: Optional[int] = None
    
    # Transcription
    transcription: Optional[str] = None
    transcribed_at: Optional[datetime] = None
    transcription_status: ProcessingStatus = ProcessingStatus.PENDING
    transcription_error: Optional[str] = None
    
    # LLM Analysis
    analysis: Optional[FeedbackAnalysis] = None
    analyzed_at: Optional[datetime] = None
    analysis_status: ProcessingStatus = ProcessingStatus.PENDING
    analysis_error: Optional[str] = None
    
    # Metadata
    language: str = "hi"
    
    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str, date: lambda v: v.isoformat()}


class FeedbackListItem(BaseModel):
    """Lightweight feedback item for list views"""
    id: str
    store_id: str
    store_name: Optional[str] = None
    feedback_date: date
    submitted_at: datetime
    tone: Optional[ToneType] = None
    summary: Optional[str] = None
    transcription_status: ProcessingStatus
    analysis_status: ProcessingStatus
    
    class Config:
        json_encoders = {date: lambda v: v.isoformat()}


# ============ Daily Analytics Models ============

class ToneBreakdown(BaseModel):
    positive: int = 0
    negative: int = 0
    neutral: int = 0


class DailyAnalytics(BaseModel):
    """Pre-aggregated daily analytics"""
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    date: date
    store_id: Optional[str] = None  # None for global aggregation
    
    total_feedbacks: int = 0
    tone_breakdown: ToneBreakdown = Field(default_factory=ToneBreakdown)
    
    products_mentioned: Dict[str, int] = {}  # product_name -> count
    issues_mentioned: Dict[str, int] = {}
    actions_suggested: Dict[str, int] = {}
    
    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str, date: lambda v: v.isoformat()}


# ============ Dashboard Response Models ============

class DailySummary(BaseModel):
    """Single day summary for dashboard charts"""
    date: date
    store_id: Optional[str] = None
    total: int = 0
    positive: int = 0
    negative: int = 0
    neutral: int = 0


class TopItem(BaseModel):
    """Top N item with count"""
    name: str
    count: int


class DashboardSummary(BaseModel):
    """Complete dashboard summary response"""
    period_start: date
    period_end: date
    
    # Overall stats
    total_feedbacks: int = 0
    total_stores: int = 0
    
    # Tone breakdown
    tone_breakdown: ToneBreakdown = Field(default_factory=ToneBreakdown)
    
    # Daily breakdown for charts
    daily_breakdown: List[DailySummary] = []
    
    # Store breakdown
    store_breakdown: List[Dict] = []
    
    # Top 5s
    top_products: List[TopItem] = []
    top_issues: List[TopItem] = []
    top_actions: List[TopItem] = []


# ============ Auth Models ============

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[UserRole] = None


class LoginRequest(BaseModel):
    username: str
    password: str
