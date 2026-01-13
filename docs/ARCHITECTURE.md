# Store Feedback System - Architecture

## Overview

A retail store feedback collection and analysis system for Tarsyer, enabling store staff to record observations and managers to analyze trends.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           FRONTEND (PWA)                                │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────────────────┐   │
│  │  Staff App   │  │ Recording UI │  │    Manager Dashboard        │   │
│  │  - Login     │  │ - Audio Rec  │  │  - Charts & Analytics       │   │
│  │  - Store ID  │  │ - File Upload│  │  - Transcription View       │   │
│  └──────────────┘  └──────────────┘  └─────────────────────────────┘   │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │ HTTPS
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    BACKEND (FastAPI on store-feedback.tarsyer.com)      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐  │
│  │  Auth API    │  │  Upload API  │  │ Dashboard API│  │ Webhook API│  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └────────────┘  │
│                                 │                                       │
│  ┌──────────────────────────────┴──────────────────────────────────┐   │
│  │                     Background Workers                           │   │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │   │
│  │  │ Transcription   │  │  LLM Analysis   │  │  Aggregation    │  │   │
│  │  │ (whisper.cpp)   │  │  (Qwen3 API)    │  │  (Daily Stats)  │  │   │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          DATA LAYER                                     │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────┐  │
│  │    MongoDB       │  │   File Storage   │  │   Redis (Optional)   │  │
│  │  - feedbacks     │  │  - /uploads/     │  │   - Job Queue        │  │
│  │  - stores        │  │  - GCP Bucket    │  │   - Caching          │  │
│  │  - users         │  │    (future)      │  │                      │  │
│  │  - analytics     │  │                  │  │                      │  │
│  └──────────────────┘  └──────────────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

## Data Flow

1. **Staff Recording Flow**
   ```
   Staff Login → Select Date → Record/Upload Audio → Submit
        ↓
   Backend receives file → Stores in /uploads/{store_id}/{date}/
        ↓
   Creates pending feedback record in MongoDB
        ↓
   Triggers transcription worker (whisper.cpp)
        ↓
   Updates record with transcription
        ↓
   Triggers LLM analysis (Qwen3 API)
        ↓
   Updates record with analysis (tone, products, issues, actions)
   ```

2. **Manager Dashboard Flow**
   ```
   Manager Login → Dashboard View
        ↓
   Fetches aggregated analytics from MongoDB
        ↓
   Displays: Daily counts, Tone breakdown, Top 5s
        ↓
   Click to drill-down: View transcription, Play audio
   ```

## MongoDB Collections

### feedbacks
```javascript
{
  _id: ObjectId,
  store_id: "W001",
  store_name: "Store Name",
  date: ISODate("2025-01-12"),
  submitted_at: ISODate("2025-01-12T10:30:00Z"),
  audio_url: "/uploads/W001/2025-01-12/audio_123.mp3",
  audio_duration_seconds: 45,
  
  // Transcription (added by worker)
  transcription: "Full transcription text...",
  transcribed_at: ISODate,
  transcription_status: "pending|completed|failed",
  
  // LLM Analysis (added by worker)
  analysis: {
    summary: "Brief summary of feedback",
    tone: "positive|negative|neutral",
    tone_score: 0.85,
    products: ["Product A", "Product B"],
    issues: ["Stock shortage", "Display problem"],
    actions: ["Restock Product A", "Fix display"],
    keywords: ["customer", "quality", "stock"]
  },
  analysis_status: "pending|completed|failed",
  analyzed_at: ISODate,
  
  // Metadata
  submitted_by: "user_id",
  language: "hi"  // Hindi transcription
}
```

### stores
```javascript
{
  _id: ObjectId,
  store_id: "W001",
  store_name: "Bata Phoenix Mall",
  region: "Chennai",
  zone: "South",
  active: true
}
```

### users
```javascript
{
  _id: ObjectId,
  username: "staff001",
  password_hash: "...",
  role: "staff|manager|admin",
  store_ids: ["W001", "W002"],  // For staff
  name: "John Doe"
}
```

### daily_analytics (pre-aggregated for dashboard)
```javascript
{
  _id: ObjectId,
  date: ISODate("2025-01-12"),
  store_id: "W001",
  
  total_feedbacks: 5,
  tone_breakdown: {
    positive: 3,
    negative: 1,
    neutral: 1
  },
  
  products_mentioned: {
    "Product A": 4,
    "Product B": 2
  },
  issues_mentioned: {
    "Stock shortage": 3,
    "Display": 1
  },
  actions_suggested: {
    "Restock": 3,
    "Training": 1
  }
}
```

## API Endpoints

### Authentication
- `POST /api/auth/login` - Login with username/password
- `POST /api/auth/refresh` - Refresh JWT token
- `GET /api/auth/me` - Get current user info

### Feedback Submission (Staff)
- `POST /api/feedback/upload` - Upload audio/video file
- `GET /api/feedback/my` - Get my submitted feedbacks

### Dashboard (Manager)
- `GET /api/dashboard/summary` - Last 15 days summary
- `GET /api/dashboard/daily?start=&end=` - Daily breakdown
- `GET /api/dashboard/feedbacks?store=&date=` - List feedbacks
- `GET /api/feedback/{id}` - Get single feedback detail
- `GET /api/feedback/{id}/audio` - Stream audio file

### Admin
- `GET /api/stores` - List all stores
- `POST /api/stores` - Add new store
- `GET /api/users` - List users
- `POST /api/users` - Create user

## Technology Stack

| Component | Technology |
|-----------|------------|
| Frontend | React + TypeScript + Vite + PWA |
| UI Components | Tailwind CSS + Recharts |
| Backend | FastAPI (Python) |
| Database | MongoDB |
| Transcription | whisper.cpp (local) |
| LLM Analysis | Qwen3 API (kwen.tarsyer.com) |
| File Storage | Local → GCP Bucket |
| Authentication | JWT |
| Process Manager | PM2 |

## Deployment

```bash
# Backend (PM2)
pm2 start ecosystem.config.js

# Frontend (served by Nginx or as static files)
npm run build
# Deploy dist/ to CDN or serve via backend
```

## Future Enhancements

1. **GCP Storage Integration** - Move file storage to GCP bucket
2. **Real-time Updates** - WebSocket for live dashboard updates
3. **Multi-language Support** - Detect and transcribe multiple languages
4. **Video Support** - Extract audio from video files
5. **Sentiment Trends** - Track sentiment changes over time
6. **Export Reports** - PDF/Excel export of analytics
7. **Push Notifications** - Alert managers on critical issues
