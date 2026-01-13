"""
Feedback upload and management API routes
"""
import os
import uuid
from datetime import datetime, date
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from fastapi.responses import FileResponse, StreamingResponse

from app.core.config import get_settings
from app.models.schemas import (
    Feedback, FeedbackCreate, FeedbackListItem, 
    ProcessingStatus
)
from app.services.auth import get_current_active_user, require_staff, require_manager
from app.services.database import get_database
from bson import ObjectId

router = APIRouter(prefix="/feedback", tags=["Feedback"])
settings = get_settings()


def validate_file_extension(filename: str) -> bool:
    """Check if file extension is allowed"""
    ext = Path(filename).suffix.lower()
    return ext in settings.ALLOWED_EXTENSIONS


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_feedback(
    file: UploadFile = File(...),
    store_id: str = Form(..., pattern=r'^W\d{3}$'),
    feedback_date: date = Form(...),
    notes: Optional[str] = Form(None),
    db = Depends(get_database),
    current_user: dict = Depends(require_staff)
):
    """
    Upload audio/video feedback file
    
    - **file**: Audio or video file (mp3, mp4, m4a, wav, etc.)
    - **store_id**: Store ID in WXXX format
    - **feedback_date**: Date of the feedback observation
    - **notes**: Optional text notes
    """
    # Validate file extension
    if not validate_file_extension(file.filename):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not allowed. Supported: {', '.join(settings.ALLOWED_EXTENSIONS)}"
        )
    
    # Check file size
    file.file.seek(0, 2)  # Seek to end
    file_size = file.file.tell()
    file.file.seek(0)  # Seek back to start
    
    max_size = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    if file_size > max_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum size: {settings.MAX_FILE_SIZE_MB}MB"
        )
    
    # Check if user has access to this store (for staff users)
    user_role = current_user.get("role", "staff")
    user_stores = current_user.get("store_ids", [])
    
    if user_role == "staff" and store_id not in user_stores:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You don't have access to store {store_id}"
        )
    
    # Get store info
    store = await db.stores.find_one({"store_id": store_id})
    store_name = store.get("store_name", "") if store else ""
    
    # Create directory structure: uploads/{store_id}/{date}/
    date_str = feedback_date.isoformat()
    upload_dir = Path(settings.UPLOAD_DIR) / store_id / date_str
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate unique filename
    file_ext = Path(file.filename).suffix.lower()
    unique_filename = f"{uuid.uuid4().hex}{file_ext}"
    file_path = upload_dir / unique_filename
    
    # Save file
    try:
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save file: {str(e)}"
        )
    
    # Create feedback record
    audio_url = f"/uploads/{store_id}/{date_str}/{unique_filename}"
    
    feedback_doc = {
        "store_id": store_id,
        "store_name": store_name,
        "feedback_date": datetime.combine(feedback_date, datetime.min.time()),
        "submitted_at": datetime.utcnow(),
        "submitted_by": current_user["username"],
        "notes": notes,
        
        # File info
        "audio_url": audio_url,
        "audio_filename": file.filename,
        "file_size_bytes": file_size,
        
        # Processing status
        "transcription_status": ProcessingStatus.PENDING.value,
        "analysis_status": ProcessingStatus.PENDING.value,
        
        "language": "hi"
    }
    
    result = await db.feedbacks.insert_one(feedback_doc)
    
    return {
        "id": str(result.inserted_id),
        "store_id": store_id,
        "feedback_date": date_str,
        "audio_url": audio_url,
        "status": "uploaded",
        "message": "Feedback uploaded successfully. Transcription will be processed shortly."
    }


@router.get("/my")
async def get_my_feedbacks(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db = Depends(get_database),
    current_user: dict = Depends(require_staff)
):
    """
    Get feedbacks submitted by the current user
    """
    query = {"submitted_by": current_user["username"]}
    
    total = await db.feedbacks.count_documents(query)
    
    feedbacks = await db.feedbacks.find(query)\
        .sort("submitted_at", -1)\
        .skip(offset)\
        .limit(limit)\
        .to_list(length=None)
    
    items = []
    for fb in feedbacks:
        analysis = fb.get("analysis", {})
        items.append({
            "id": str(fb["_id"]),
            "store_id": fb["store_id"],
            "store_name": fb.get("store_name", ""),
            "feedback_date": fb["feedback_date"].date().isoformat() if fb.get("feedback_date") else None,
            "submitted_at": fb["submitted_at"].isoformat() if fb.get("submitted_at") else None,
            "tone": analysis.get("tone"),
            "summary": analysis.get("summary"),
            "transcription_status": fb.get("transcription_status", "pending"),
            "analysis_status": fb.get("analysis_status", "pending")
        })
    
    return {
        "total": total,
        "items": items
    }


@router.get("/{feedback_id}")
async def get_feedback_detail(
    feedback_id: str,
    db = Depends(get_database),
    current_user: dict = Depends(require_staff)
):
    """
    Get detailed feedback information including transcription and analysis
    """
    if not ObjectId.is_valid(feedback_id):
        raise HTTPException(status_code=400, detail="Invalid feedback ID")
    
    feedback = await db.feedbacks.find_one({"_id": ObjectId(feedback_id)})
    
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")
    
    # Check access
    user_role = current_user.get("role", "staff")
    user_stores = current_user.get("store_ids", [])
    
    if user_role == "staff":
        # Staff can only see their own feedbacks or feedbacks from their stores
        if (feedback.get("submitted_by") != current_user["username"] and 
            feedback.get("store_id") not in user_stores):
            raise HTTPException(status_code=403, detail="Access denied")
    
    # Format response
    feedback["id"] = str(feedback.pop("_id"))
    if feedback.get("feedback_date"):
        feedback["feedback_date"] = feedback["feedback_date"].date().isoformat()
    if feedback.get("submitted_at"):
        feedback["submitted_at"] = feedback["submitted_at"].isoformat()
    if feedback.get("transcribed_at"):
        feedback["transcribed_at"] = feedback["transcribed_at"].isoformat()
    if feedback.get("analyzed_at"):
        feedback["analyzed_at"] = feedback["analyzed_at"].isoformat()
    
    return feedback


@router.get("/{feedback_id}/audio")
async def get_feedback_audio(
    feedback_id: str,
    db = Depends(get_database),
    current_user: dict = Depends(require_staff)
):
    """
    Stream the audio file for a feedback
    """
    if not ObjectId.is_valid(feedback_id):
        raise HTTPException(status_code=400, detail="Invalid feedback ID")
    
    feedback = await db.feedbacks.find_one({"_id": ObjectId(feedback_id)})
    
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")
    
    audio_url = feedback.get("audio_url", "")
    if not audio_url:
        raise HTTPException(status_code=404, detail="Audio file not found")
    
    # Convert URL to file path
    file_path = Path(settings.UPLOAD_DIR) / audio_url.replace("/uploads/", "")
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found on disk")
    
    # Determine content type
    ext = file_path.suffix.lower()
    content_types = {
        ".mp3": "audio/mpeg",
        ".mp4": "video/mp4",
        ".m4a": "audio/mp4",
        ".wav": "audio/wav",
        ".webm": "audio/webm",
        ".ogg": "audio/ogg",
        ".flac": "audio/flac",
        ".aac": "audio/aac"
    }
    content_type = content_types.get(ext, "application/octet-stream")
    
    return FileResponse(
        file_path,
        media_type=content_type,
        filename=feedback.get("audio_filename", file_path.name)
    )


@router.post("/{feedback_id}/retry-transcription")
async def retry_transcription(
    feedback_id: str,
    db = Depends(get_database),
    current_user: dict = Depends(require_manager)
):
    """
    Retry failed transcription (manager only)
    """
    if not ObjectId.is_valid(feedback_id):
        raise HTTPException(status_code=400, detail="Invalid feedback ID")
    
    result = await db.feedbacks.update_one(
        {"_id": ObjectId(feedback_id)},
        {
            "$set": {
                "transcription_status": ProcessingStatus.PENDING.value,
                "transcription_error": None
            }
        }
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Feedback not found")
    
    return {"status": "queued", "message": "Transcription will be retried"}


@router.post("/{feedback_id}/retry-analysis")
async def retry_analysis(
    feedback_id: str,
    db = Depends(get_database),
    current_user: dict = Depends(require_manager)
):
    """
    Retry failed LLM analysis (manager only)
    """
    if not ObjectId.is_valid(feedback_id):
        raise HTTPException(status_code=400, detail="Invalid feedback ID")
    
    result = await db.feedbacks.update_one(
        {"_id": ObjectId(feedback_id)},
        {
            "$set": {
                "analysis_status": ProcessingStatus.PENDING.value,
                "analysis_error": None
            }
        }
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Feedback not found")
    
    return {"status": "queued", "message": "Analysis will be retried"}
