"""
Dashboard and Analytics API routes
"""
from datetime import datetime, date, timedelta
from typing import Optional, List
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, Query
from bson import ObjectId

from app.models.schemas import (
    DashboardSummary, DailySummary, TopItem, ToneBreakdown,
    ProcessingStatus
)
from app.services.auth import require_manager, get_current_active_user
from app.services.database import get_database

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/summary", response_model=DashboardSummary)
async def get_dashboard_summary(
    days: int = Query(15, ge=1, le=90, description="Number of days to include"),
    store_id: Optional[str] = Query(None, pattern=r'^W\d{3}$', description="Filter by store"),
    db = Depends(get_database),
    current_user: dict = Depends(require_manager)
):
    """
    Get comprehensive dashboard summary for the last N days
    
    Returns:
    - Total feedbacks count
    - Tone breakdown (positive/negative/neutral)
    - Daily breakdown for charts
    - Store-wise breakdown
    - Top 5 products, issues, and actions
    """
    end_date = date.today()
    start_date = end_date - timedelta(days=days - 1)
    
    # Build query filter
    query = {
        "feedback_date": {
            "$gte": datetime.combine(start_date, datetime.min.time()),
            "$lte": datetime.combine(end_date, datetime.max.time())
        },
        "analysis_status": ProcessingStatus.COMPLETED.value
    }
    
    if store_id:
        query["store_id"] = store_id
    
    # Fetch all analyzed feedbacks for the period
    feedbacks = await db.feedbacks.find(query).to_list(length=None)
    
    # Initialize counters
    total_feedbacks = len(feedbacks)
    tone_counts = Counter()
    daily_data = {}
    store_data = {}
    all_products = Counter()
    all_issues = Counter()
    all_actions = Counter()
    
    stores_seen = set()
    
    # Process each feedback
    for fb in feedbacks:
        fb_date = fb["feedback_date"].date() if fb.get("feedback_date") else None
        fb_store = fb.get("store_id", "unknown")
        analysis = fb.get("analysis", {})
        tone = analysis.get("tone", "neutral")
        
        stores_seen.add(fb_store)
        
        # Count tones
        tone_counts[tone] += 1
        
        # Daily breakdown
        if fb_date:
            date_key = fb_date.isoformat()
            if date_key not in daily_data:
                daily_data[date_key] = {
                    "date": fb_date,
                    "total": 0,
                    "positive": 0,
                    "negative": 0,
                    "neutral": 0
                }
            daily_data[date_key]["total"] += 1
            daily_data[date_key][tone] += 1
        
        # Store breakdown
        if fb_store not in store_data:
            store_data[fb_store] = {
                "store_id": fb_store,
                "store_name": fb.get("store_name", fb_store),
                "total": 0,
                "positive": 0,
                "negative": 0,
                "neutral": 0
            }
        store_data[fb_store]["total"] += 1
        store_data[fb_store][tone] += 1
        
        # Aggregate products, issues, actions
        for product in analysis.get("products", []):
            if product:
                all_products[product.strip().lower()] += 1
        
        for issue in analysis.get("issues", []):
            if issue:
                all_issues[issue.strip().lower()] += 1
        
        for action in analysis.get("actions", []):
            if action:
                all_actions[action.strip().lower()] += 1
    
    # Build daily breakdown sorted by date
    daily_breakdown = []
    current = start_date
    while current <= end_date:
        date_key = current.isoformat()
        if date_key in daily_data:
            daily_breakdown.append(DailySummary(
                date=current,
                total=daily_data[date_key]["total"],
                positive=daily_data[date_key]["positive"],
                negative=daily_data[date_key]["negative"],
                neutral=daily_data[date_key]["neutral"]
            ))
        else:
            daily_breakdown.append(DailySummary(
                date=current,
                total=0,
                positive=0,
                negative=0,
                neutral=0
            ))
        current += timedelta(days=1)
    
    # Build store breakdown sorted by total
    store_breakdown = sorted(
        list(store_data.values()),
        key=lambda x: x["total"],
        reverse=True
    )
    
    # Get top 5 items
    def get_top_5(counter: Counter) -> List[TopItem]:
        return [
            TopItem(name=name.title(), count=count)
            for name, count in counter.most_common(5)
        ]
    
    return DashboardSummary(
        period_start=start_date,
        period_end=end_date,
        total_feedbacks=total_feedbacks,
        total_stores=len(stores_seen),
        tone_breakdown=ToneBreakdown(
            positive=tone_counts.get("positive", 0),
            negative=tone_counts.get("negative", 0),
            neutral=tone_counts.get("neutral", 0)
        ),
        daily_breakdown=daily_breakdown,
        store_breakdown=store_breakdown,
        top_products=get_top_5(all_products),
        top_issues=get_top_5(all_issues),
        top_actions=get_top_5(all_actions)
    )


@router.get("/daily")
async def get_daily_breakdown(
    start_date: date = Query(..., description="Start date"),
    end_date: date = Query(..., description="End date"),
    store_id: Optional[str] = Query(None, pattern=r'^W\d{3}$'),
    db = Depends(get_database),
    current_user: dict = Depends(require_manager)
):
    """
    Get detailed daily breakdown for a date range
    """
    if (end_date - start_date).days > 90:
        raise HTTPException(
            status_code=400,
            detail="Date range cannot exceed 90 days"
        )
    
    query = {
        "feedback_date": {
            "$gte": datetime.combine(start_date, datetime.min.time()),
            "$lte": datetime.combine(end_date, datetime.max.time())
        }
    }
    
    if store_id:
        query["store_id"] = store_id
    
    # Aggregation pipeline
    pipeline = [
        {"$match": query},
        {
            "$group": {
                "_id": {
                    "date": {"$dateToString": {"format": "%Y-%m-%d", "date": "$feedback_date"}},
                    "store_id": "$store_id"
                },
                "total": {"$sum": 1},
                "completed": {
                    "$sum": {"$cond": [{"$eq": ["$analysis_status", "completed"]}, 1, 0]}
                },
                "pending": {
                    "$sum": {"$cond": [{"$eq": ["$analysis_status", "pending"]}, 1, 0]}
                }
            }
        },
        {"$sort": {"_id.date": 1}}
    ]
    
    results = await db.feedbacks.aggregate(pipeline).to_list(length=None)
    
    # Format results
    formatted = []
    for item in results:
        formatted.append({
            "date": item["_id"]["date"],
            "store_id": item["_id"]["store_id"],
            "total": item["total"],
            "completed": item["completed"],
            "pending": item["pending"]
        })
    
    return formatted


@router.get("/feedbacks")
async def get_feedbacks_list(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    store_id: Optional[str] = Query(None, pattern=r'^W\d{3}$'),
    tone: Optional[str] = Query(None, pattern=r'^(positive|negative|neutral)$'),
    status: Optional[str] = Query(None, pattern=r'^(pending|completed|failed)$'),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db = Depends(get_database),
    current_user: dict = Depends(require_manager)
):
    """
    Get filtered list of feedbacks for the dashboard
    """
    query = {}
    
    # Date range filter
    if start_date or end_date:
        query["feedback_date"] = {}
        if start_date:
            query["feedback_date"]["$gte"] = datetime.combine(start_date, datetime.min.time())
        if end_date:
            query["feedback_date"]["$lte"] = datetime.combine(end_date, datetime.max.time())
    
    # Store filter
    if store_id:
        query["store_id"] = store_id
    
    # Tone filter
    if tone:
        query["analysis.tone"] = tone
    
    # Status filter
    if status:
        query["analysis_status"] = status
    
    # Get total count
    total = await db.feedbacks.count_documents(query)
    
    # Get feedbacks
    feedbacks = await db.feedbacks.find(query)\
        .sort("feedback_date", -1)\
        .skip(offset)\
        .limit(limit)\
        .to_list(length=None)
    
    # Format response
    items = []
    for fb in feedbacks:
        analysis = fb.get("analysis", {})
        items.append({
            "id": str(fb["_id"]),
            "store_id": fb.get("store_id"),
            "store_name": fb.get("store_name", ""),
            "feedback_date": fb["feedback_date"].date().isoformat() if fb.get("feedback_date") else None,
            "submitted_at": fb["submitted_at"].isoformat() if fb.get("submitted_at") else None,
            "submitted_by": fb.get("submitted_by"),
            "tone": analysis.get("tone"),
            "tone_score": analysis.get("tone_score"),
            "summary": analysis.get("summary"),
            "products": analysis.get("products", []),
            "issues": analysis.get("issues", []),
            "actions": analysis.get("actions", []),
            "transcription_status": fb.get("transcription_status", "pending"),
            "analysis_status": fb.get("analysis_status", "pending"),
            "audio_url": fb.get("audio_url")
        })
    
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": items
    }


@router.get("/stores")
async def get_stores_summary(
    days: int = Query(15, ge=1, le=90),
    db = Depends(get_database),
    current_user: dict = Depends(require_manager)
):
    """
    Get summary of feedback activity by store
    """
    end_date = date.today()
    start_date = end_date - timedelta(days=days - 1)
    
    pipeline = [
        {
            "$match": {
                "feedback_date": {
                    "$gte": datetime.combine(start_date, datetime.min.time()),
                    "$lte": datetime.combine(end_date, datetime.max.time())
                }
            }
        },
        {
            "$group": {
                "_id": "$store_id",
                "store_name": {"$first": "$store_name"},
                "total_feedbacks": {"$sum": 1},
                "last_feedback": {"$max": "$feedback_date"}
            }
        },
        {"$sort": {"total_feedbacks": -1}}
    ]
    
    results = await db.feedbacks.aggregate(pipeline).to_list(length=None)
    
    # Get all stores for comparison
    all_stores = await db.stores.find({"active": True}).to_list(length=None)
    stores_with_feedback = {r["_id"] for r in results}
    
    # Add stores with no feedback
    for store in all_stores:
        if store["store_id"] not in stores_with_feedback:
            results.append({
                "_id": store["store_id"],
                "store_name": store.get("store_name", ""),
                "total_feedbacks": 0,
                "last_feedback": None
            })
    
    # Format response
    formatted = []
    for r in results:
        formatted.append({
            "store_id": r["_id"],
            "store_name": r.get("store_name", r["_id"]),
            "total_feedbacks": r["total_feedbacks"],
            "last_feedback": r["last_feedback"].isoformat() if r.get("last_feedback") else None
        })
    
    return formatted


@router.get("/processing-status")
async def get_processing_status(
    db = Depends(get_database),
    current_user: dict = Depends(require_manager)
):
    """
    Get overview of processing queue status
    """
    # Transcription status
    transcription_pending = await db.feedbacks.count_documents({
        "transcription_status": ProcessingStatus.PENDING.value
    })
    transcription_processing = await db.feedbacks.count_documents({
        "transcription_status": ProcessingStatus.PROCESSING.value
    })
    transcription_failed = await db.feedbacks.count_documents({
        "transcription_status": ProcessingStatus.FAILED.value
    })
    
    # Analysis status
    analysis_pending = await db.feedbacks.count_documents({
        "transcription_status": ProcessingStatus.COMPLETED.value,
        "analysis_status": ProcessingStatus.PENDING.value
    })
    analysis_processing = await db.feedbacks.count_documents({
        "analysis_status": ProcessingStatus.PROCESSING.value
    })
    analysis_failed = await db.feedbacks.count_documents({
        "analysis_status": ProcessingStatus.FAILED.value
    })
    
    return {
        "transcription": {
            "pending": transcription_pending,
            "processing": transcription_processing,
            "failed": transcription_failed
        },
        "analysis": {
            "pending": analysis_pending,
            "processing": analysis_processing,
            "failed": analysis_failed
        }
    }
