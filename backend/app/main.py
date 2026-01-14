#!/usr/bin/env python3
"""
Store Feedback API - Main Application with JWT Authentication
Handles audio/video uploads, transcription, AI analysis, and dashboard data
"""
import os
import uuid
from datetime import datetime, timedelta
from typing import Optional, List
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from jose import JWTError, jwt
from passlib.context import CryptContext

# Load environment variables from .env file
load_dotenv()

# Configuration
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "store_feedback")
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/data/uploads")
BASE_URL = os.getenv("BASE_URL", "https://store-feedback.tarsyer.com")

# JWT Configuration
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))

# Ensure upload directory exists
os.makedirs(UPLOAD_DIR, exist_ok=True)

# MongoDB client
db_client: Optional[AsyncIOMotorClient] = None

# Auth setup
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle - DB connections"""
    global db_client
    db_client = AsyncIOMotorClient(MONGO_URI)
    # Create indexes
    db = db_client[DB_NAME]
    await db.feedbacks.create_index([("store_code", 1), ("recorded_date", -1)])
    await db.feedbacks.create_index([("created_at", -1)])
    await db.feedbacks.create_index([("status", 1)])
    await db.users.create_index([("username", 1)], unique=True)
    print("✓ Connected to MongoDB")
    yield
    db_client.close()
    print("✓ Disconnected from MongoDB")


app = FastAPI(
    title="Store Feedback API",
    description="API for collecting and analyzing retail store staff feedback",
    version="1.0.0",
    lifespan=lifespan
)

# CORS for PWA
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve uploaded media files
app.mount("/media", StaticFiles(directory=UPLOAD_DIR), name="media")


# ============ Pydantic Models ============

class StoreInfo(BaseModel):
    store_code: str = Field(..., pattern=r'^W\d{3}$', description="Store code in WXXX format")
    store_name: Optional[str] = None


class AnalysisResult(BaseModel):
    summary: str = ""
    tone: str = "neutral"  # positive, negative, neutral
    tone_score: float = 0.5  # 0-1 scale
    products: List[str] = []
    issues: List[str] = []
    actions: List[str] = []
    keywords: List[str] = []


class FeedbackCreate(BaseModel):
    store_code: str
    recorded_date: str  # YYYY-MM-DD
    notes: Optional[str] = None


class FeedbackResponse(BaseModel):
    id: str
    store_code: str
    store_name: Optional[str]
    recorded_date: str
    recorded_time: str
    media_url: Optional[str]
    media_type: Optional[str]
    transcription: Optional[str]
    analysis: Optional[AnalysisResult]
    status: str  # pending, transcribing, analyzing, completed, error
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        json_encoders = {ObjectId: str}


class DashboardStats(BaseModel):
    total_feedbacks: int
    feedbacks_by_day: List[dict]
    feedbacks_by_store: List[dict]
    tone_distribution: dict
    top_products: List[dict]
    top_issues: List[dict]
    top_actions: List[dict]


class Token(BaseModel):
    access_token: str
    token_type: str


class LoginRequest(BaseModel):
    username: str
    password: str


# ============ Auth Helper Functions ============

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt


async def get_user_by_username(db, username: str) -> Optional[dict]:
    """Get user from database by username"""
    return await db.users.find_one({"username": username})


async def authenticate_user(db, username: str, password: str) -> Optional[dict]:
    """Authenticate user with username and password"""
    user = await get_user_by_username(db, username)
    if not user:
        return None
    if not verify_password(password, user.get("password_hash", "")):
        return None
    return user


async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """Get current user from JWT token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    db = get_db()

    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = await get_user_by_username(db, username)
    if user is None:
        raise credentials_exception

    return user


async def get_current_active_user(current_user: dict = Depends(get_current_user)) -> dict:
    """Ensure user is active"""
    if current_user.get("disabled", False):
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


def require_role(required_roles: list):
    """Dependency to require specific roles"""
    async def role_checker(current_user: dict = Depends(get_current_active_user)):
        user_role = current_user.get("role", "staff")
        if user_role not in required_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user_role}' not authorized"
            )
        return current_user
    return role_checker


# Role-based dependencies
require_manager = require_role(["manager", "admin"])
require_admin = require_role(["admin"])


# ============ Helper Functions ============

def get_db():
    return db_client[DB_NAME]


def serialize_feedback(doc: dict) -> dict:
    """Convert MongoDB document to response format"""
    return {
        "id": str(doc["_id"]),
        "store_code": doc.get("store_code"),
        "store_name": doc.get("store_name"),
        "recorded_date": doc.get("recorded_date"),
        "recorded_time": doc.get("recorded_time", ""),
        "media_url": doc.get("media_url"),
        "media_type": doc.get("media_type"),
        "transcription": doc.get("transcription"),
        "analysis": doc.get("analysis"),
        "status": doc.get("status", "pending"),
        "error_message": doc.get("error_message"),
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }


# ============ API Endpoints ============

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


# ============ Authentication Endpoints ============

@app.post("/api/v1/auth/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Login with username and password (form data)"""
    db = get_db()
    user = await authenticate_user(db, form_data.username, form_data.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": user["username"],
            "role": user.get("role", "staff"),
            "name": user.get("name", ""),
            "store_ids": user.get("store_ids", [])
        },
        expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/api/v1/auth/login/json", response_model=Token)
async def login_json(login_data: LoginRequest):
    """Login with JSON body (for web/mobile apps)"""
    db = get_db()
    user = await authenticate_user(db, login_data.username, login_data.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": user["username"],
            "role": user.get("role", "staff"),
            "name": user.get("name", ""),
            "store_ids": user.get("store_ids", [])
        },
        expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/api/v1/auth/me")
async def get_current_user_info(current_user: dict = Depends(get_current_active_user)):
    """Get current user information"""
    return {
        "username": current_user["username"],
        "name": current_user.get("name", ""),
        "role": current_user.get("role", "staff"),
        "store_ids": current_user.get("store_ids", [])
    }


# ============ Feedback Endpoints ============

@app.post("/api/v1/feedback", response_model=FeedbackResponse)
async def upload_feedback(
    store_code: str = Form(..., pattern=r'^W\d{3}$'),
    recorded_date: str = Form(...),  # YYYY-MM-DD
    notes: Optional[str] = Form(None),
    media: UploadFile = File(...)
):
    """
    Upload a new feedback recording from store staff.
    Accepts audio/video files and queues for transcription.
    """
    db = get_db()

    # Validate file type
    allowed_types = {
        'audio/mpeg', 'audio/mp3', 'audio/mp4', 'audio/wav', 'audio/webm',
        'audio/ogg', 'audio/flac', 'audio/aac', 'audio/m4a',
        'video/mp4', 'video/webm', 'video/quicktime'
    }

    content_type = media.content_type or ""
    if not any(t in content_type for t in ['audio', 'video']):
        raise HTTPException(400, "Invalid file type. Only audio/video files allowed.")

    # Generate unique filename
    ext = os.path.splitext(media.filename)[1] or '.mp3'
    unique_id = uuid.uuid4().hex[:12]
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"{store_code}_{timestamp}_{unique_id}{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)

    # Save file
    try:
        content = await media.read()
        with open(filepath, "wb") as f:
            f.write(content)
    except Exception as e:
        raise HTTPException(500, f"Failed to save file: {str(e)}")

    # Create feedback document
    now = datetime.utcnow()
    feedback_doc = {
        "store_code": store_code.upper(),
        "store_name": None,  # Can be enriched from store master
        "recorded_date": recorded_date,
        "recorded_time": now.strftime("%H:%M:%S"),
        "media_filename": filename,
        "media_url": f"{BASE_URL}/media/{filename}",
        "media_type": "audio" if "audio" in content_type else "video",
        "notes": notes,
        "transcription": None,
        "analysis": None,
        "status": "pending",
        "error_message": None,
        "created_at": now,
        "updated_at": now,
    }

    result = await db.feedbacks.insert_one(feedback_doc)
    feedback_doc["_id"] = result.inserted_id

    return serialize_feedback(feedback_doc)


@app.get("/api/v1/feedback/{feedback_id}", response_model=FeedbackResponse)
async def get_feedback(feedback_id: str):
    """Get a specific feedback by ID"""
    db = get_db()

    try:
        doc = await db.feedbacks.find_one({"_id": ObjectId(feedback_id)})
    except:
        raise HTTPException(400, "Invalid feedback ID")

    if not doc:
        raise HTTPException(404, "Feedback not found")

    return serialize_feedback(doc)


@app.get("/api/v1/feedbacks", response_model=List[FeedbackResponse])
async def list_feedbacks(
    store_code: Optional[str] = Query(None, pattern=r'^W\d{3}$'),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    skip: int = Query(0)
):
    """List feedbacks with optional filters"""
    db = get_db()

    query = {}
    if store_code:
        query["store_code"] = store_code.upper()
    if status:
        query["status"] = status
    if start_date or end_date:
        date_query = {}
        if start_date:
            date_query["$gte"] = start_date
        if end_date:
            date_query["$lte"] = end_date
        if date_query:
            query["recorded_date"] = date_query

    cursor = db.feedbacks.find(query).sort("created_at", -1).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)

    return [serialize_feedback(doc) for doc in docs]


@app.get("/api/v1/dashboard/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    days: int = Query(15, le=90),
    store_code: Optional[str] = Query(None),
    current_user: dict = Depends(require_manager)
):
    """
    Get dashboard statistics for the last N days.
    Requires manager or admin role.
    """
    db = get_db()

    # Date range
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=days)

    # Base match
    match_stage = {
        "recorded_date": {
            "$gte": start_date.isoformat(),
            "$lte": end_date.isoformat()
        }
    }
    if store_code:
        match_stage["store_code"] = store_code.upper()

    # Total count
    total = await db.feedbacks.count_documents(match_stage)

    # Feedbacks by day
    by_day_pipeline = [
        {"$match": match_stage},
        {"$group": {
            "_id": "$recorded_date",
            "count": {"$sum": 1}
        }},
        {"$sort": {"_id": 1}}
    ]
    by_day = await db.feedbacks.aggregate(by_day_pipeline).to_list(length=days+1)

    # Feedbacks by store
    by_store_pipeline = [
        {"$match": match_stage},
        {"$group": {
            "_id": "$store_code",
            "count": {"$sum": 1}
        }},
        {"$sort": {"count": -1}},
        {"$limit": 20}
    ]
    by_store = await db.feedbacks.aggregate(by_store_pipeline).to_list(length=20)

    # Tone distribution (only completed feedbacks)
    tone_match = {**match_stage, "status": "completed", "analysis.tone": {"$exists": True}}
    tone_pipeline = [
        {"$match": tone_match},
        {"$group": {
            "_id": "$analysis.tone",
            "count": {"$sum": 1}
        }}
    ]
    tone_results = await db.feedbacks.aggregate(tone_pipeline).to_list(length=10)
    tone_dist = {item["_id"]: item["count"] for item in tone_results}

    # Top products
    products_pipeline = [
        {"$match": {**match_stage, "status": "completed"}},
        {"$unwind": "$analysis.products"},
        {"$group": {
            "_id": "$analysis.products",
            "count": {"$sum": 1}
        }},
        {"$sort": {"count": -1}},
        {"$limit": 5}
    ]
    top_products = await db.feedbacks.aggregate(products_pipeline).to_list(length=5)

    # Top issues
    issues_pipeline = [
        {"$match": {**match_stage, "status": "completed"}},
        {"$unwind": "$analysis.issues"},
        {"$group": {
            "_id": "$analysis.issues",
            "count": {"$sum": 1}
        }},
        {"$sort": {"count": -1}},
        {"$limit": 5}
    ]
    top_issues = await db.feedbacks.aggregate(issues_pipeline).to_list(length=5)

    # Top actions
    actions_pipeline = [
        {"$match": {**match_stage, "status": "completed"}},
        {"$unwind": "$analysis.actions"},
        {"$group": {
            "_id": "$analysis.actions",
            "count": {"$sum": 1}
        }},
        {"$sort": {"count": -1}},
        {"$limit": 5}
    ]
    top_actions = await db.feedbacks.aggregate(actions_pipeline).to_list(length=5)

    return DashboardStats(
        total_feedbacks=total,
        feedbacks_by_day=[{"date": d["_id"], "count": d["count"]} for d in by_day],
        feedbacks_by_store=[{"store": s["_id"], "count": s["count"]} for s in by_store],
        tone_distribution=tone_dist,
        top_products=[{"name": p["_id"], "count": p["count"]} for p in top_products],
        top_issues=[{"name": i["_id"], "count": i["count"]} for i in top_issues],
        top_actions=[{"name": a["_id"], "count": a["count"]} for a in top_actions],
    )


@app.get("/api/v1/stores")
async def list_stores(current_user: dict = Depends(require_manager)):
    """Get list of all stores (requires manager role)"""
    db = get_db()

    pipeline = [
        {"$group": {
            "_id": "$store_code",
            "feedback_count": {"$sum": 1},
            "last_feedback": {"$max": "$created_at"}
        }},
        {"$sort": {"_id": 1}}
    ]

    stores = await db.feedbacks.aggregate(pipeline).to_list(length=500)

    return [
        {
            "store_code": s["_id"],
            "feedback_count": s["feedback_count"],
            "last_feedback": s["last_feedback"].isoformat() if s["last_feedback"] else None
        }
        for s in stores
    ]


# ============ Internal Endpoints (for worker services) ============

@app.get("/api/internal/pending")
async def get_pending_feedbacks(limit: int = 10):
    """Get feedbacks pending transcription (for worker)"""
    db = get_db()

    cursor = db.feedbacks.find({"status": "pending"}).limit(limit)
    docs = await cursor.to_list(length=limit)

    return [serialize_feedback(doc) for doc in docs]


@app.patch("/api/internal/feedback/{feedback_id}/transcription")
async def update_transcription(feedback_id: str, transcription: str = Form(...)):
    """Update feedback with transcription result"""
    db = get_db()

    result = await db.feedbacks.update_one(
        {"_id": ObjectId(feedback_id)},
        {
            "$set": {
                "transcription": transcription,
                "status": "transcribed",
                "updated_at": datetime.utcnow()
            }
        }
    )

    if result.matched_count == 0:
        raise HTTPException(404, "Feedback not found")

    return {"status": "updated"}


@app.patch("/api/internal/feedback/{feedback_id}/analysis")
async def update_analysis(feedback_id: str, analysis: AnalysisResult):
    """Update feedback with AI analysis result"""
    db = get_db()

    result = await db.feedbacks.update_one(
        {"_id": ObjectId(feedback_id)},
        {
            "$set": {
                "analysis": analysis.model_dump(),
                "status": "completed",
                "updated_at": datetime.utcnow()
            }
        }
    )

    if result.matched_count == 0:
        raise HTTPException(404, "Feedback not found")

    return {"status": "updated"}


@app.patch("/api/internal/feedback/{feedback_id}/error")
async def mark_error(feedback_id: str, error_message: str = Form(...)):
    """Mark feedback as errored"""
    db = get_db()

    result = await db.feedbacks.update_one(
        {"_id": ObjectId(feedback_id)},
        {
            "$set": {
                "status": "error",
                "error_message": error_message,
                "updated_at": datetime.utcnow()
            }
        }
    )

    if result.matched_count == 0:
        raise HTTPException(404, "Feedback not found")

    return {"status": "updated"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
