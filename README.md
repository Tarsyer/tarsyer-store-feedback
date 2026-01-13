# Store Feedback System

A complete solution for collecting, transcribing, and analyzing retail store staff feedback using AI.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     store-feedback.tarsyer.com                   │
├─────────────────────────────────────────────────────────────────┤
│                         Nginx Reverse Proxy                      │
│                    (SSL, Load Balancing, Static Files)           │
└───────────────┬─────────────────────────────┬───────────────────┘
                │                             │
        ┌───────▼───────┐           ┌─────────▼─────────┐
        │   Frontend    │           │    FastAPI        │
        │   PWA (React) │           │    Backend API    │
        │   Port 3000   │           │    Port 8000      │
        └───────────────┘           └─────────┬─────────┘
                                              │
                        ┌─────────────────────┼─────────────────────┐
                        │                     │                     │
              ┌─────────▼─────────┐ ┌─────────▼─────────┐ ┌─────────▼─────────┐
              │   Transcription   │ │   Analysis        │ │   MongoDB         │
              │   Worker          │ │   Worker          │ │   Database        │
              │   (whisper.cpp)   │ │   (Qwen3 API)     │ │   Port 27017      │
              └───────────────────┘ └───────────────────┘ └───────────────────┘
```

## Features

### Store Staff App (PWA)
- **Mobile-first design** - Works on any smartphone
- **Offline capable** - Service worker for offline access
- **Audio recording** - Direct recording from device microphone
- **File upload** - Upload existing audio/video files
- **History view** - See past submissions and their status

### Backend API
- **FastAPI** - High-performance async Python framework
- **MongoDB** - Flexible document storage
- **File storage** - Local/GCP bucket for media files
- **RESTful endpoints** - Clean API design

### Processing Pipeline
1. **Upload** - Staff submits audio via PWA
2. **Transcription** - whisper.cpp converts speech to text (Hindi → English)
3. **AI Analysis** - Qwen3 extracts:
   - Summary
   - Tone (positive/negative/neutral)
   - Product mentions
   - Issues reported
   - Suggested actions

### Manager Dashboard
- **Daily trends** - Submission counts over time
- **Store breakdown** - Feedbacks per store
- **Tone distribution** - Sentiment analysis chart
- **Top 5 insights** - Products, issues, actions
- **Detailed view** - Full transcription, audio playback
- **CSV export** - Download data for further analysis

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Or: Python 3.11+, Node.js 20+, MongoDB, whisper.cpp

### Using Docker (Recommended)

```bash
# Clone and start
cd store-feedback
docker-compose up -d

# View logs
docker-compose logs -f

# Access
# PWA: http://localhost:3000
# API: http://localhost:8000
# Dashboard: http://localhost:3000/dashboard
```

### Manual Setup

#### 1. Start MongoDB
```bash
mongod --dbpath /data/db
```

#### 2. Setup Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Start API
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

#### 3. Setup whisper.cpp
```bash
git clone https://github.com/ggerganov/whisper.cpp.git
cd whisper.cpp
cmake -B build && cmake --build build

# Download model
./models/download-ggml-model.sh medium
```

#### 4. Start Workers
```bash
# Transcription worker
export WHISPER_CLI=/path/to/whisper-cli
export WHISPER_MODEL=/path/to/ggml-medium.bin
python services/transcription_worker.py

# Analysis worker (separate terminal)
python services/analysis_worker.py
```

#### 5. Start Frontend
```bash
cd frontend
npm install
npm run dev
```

### Using PM2 (Production)

```bash
# Install PM2
npm install -g pm2

# Start all services
pm2 start ecosystem.config.js

# Monitor
pm2 monit

# Logs
pm2 logs
```

## API Reference

### Upload Feedback
```bash
curl -X POST https://store-feedback.tarsyer.com/api/v1/feedback \
  -F "store_code=W001" \
  -F "recorded_date=2025-01-12" \
  -F "media=@recording.mp3"
```

### Get Dashboard Stats
```bash
curl "https://store-feedback.tarsyer.com/api/v1/dashboard/stats?days=15"
```

### List Feedbacks
```bash
curl "https://store-feedback.tarsyer.com/api/v1/feedbacks?store_code=W001&limit=20"
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MONGO_URI` | MongoDB connection string | `mongodb://localhost:27017` |
| `DB_NAME` | Database name | `store_feedback` |
| `UPLOAD_DIR` | Media file storage path | `/data/uploads` |
| `BASE_URL` | Public URL for media links | `https://store-feedback.tarsyer.com` |
| `WHISPER_CLI` | Path to whisper-cli binary | - |
| `WHISPER_MODEL` | Path to whisper model file | - |
| `WHISPER_LANG` | Source language for transcription | `hi` (Hindi) |
| `QWEN_API_URL` | Qwen3 API endpoint | `https://kwen.tarsyer.com/v1/chat/completions` |
| `QWEN_API_KEY` | Qwen3 API key | - |
| `QWEN_TARGET_SERVER` | Qwen target server | `BK` |

## Data Schema

### Feedback Document
```json
{
  "_id": "ObjectId",
  "store_code": "W001",
  "store_name": "Bata - MG Road",
  "recorded_date": "2025-01-12",
  "recorded_time": "14:30:00",
  "media_url": "https://store-feedback.tarsyer.com/media/W001_20250112.mp3",
  "media_type": "audio",
  "transcription": "Today we had good footfall...",
  "analysis": {
    "summary": "Good day with high sales...",
    "tone": "positive",
    "tone_score": 0.85,
    "products": ["Power shoes", "Sandals"],
    "issues": ["Stock shortage"],
    "actions": ["Reorder Power shoes size 8-9"]
  },
  "status": "completed",
  "created_at": "2025-01-12T14:30:00Z",
  "updated_at": "2025-01-12T14:35:00Z"
}
```

## Deployment to GCP

### 1. Create GCP Resources
```bash
# Create storage bucket
gsutil mb gs://tarsyer-store-feedback

# Create VM instance
gcloud compute instances create store-feedback-server \
  --machine-type=e2-medium \
  --zone=asia-south1-a \
  --image-family=ubuntu-2204-lts
```

### 2. Setup SSL (Let's Encrypt)
```bash
certbot certonly --nginx -d store-feedback.tarsyer.com
```

### 3. Configure DNS
Point `store-feedback.tarsyer.com` to your server IP.

## Future Enhancements

- [ ] GCP Storage bucket integration
- [ ] User authentication (store staff login)
- [ ] Push notifications for managers
- [ ] Real-time WebSocket updates
- [ ] Multi-language support
- [ ] Sentiment trends over time
- [ ] Store comparison reports
- [ ] Mobile app (React Native)

## Troubleshooting

### Audio not transcribing
1. Check whisper.cpp installation: `whisper-cli --help`
2. Verify model file exists
3. Check worker logs: `pm2 logs transcription-worker`

### Analysis failing
1. Verify Qwen API key
2. Check API connectivity: `curl https://kwen.tarsyer.com/health`
3. Check worker logs: `pm2 logs analysis-worker`

### Upload errors
1. Check file size (max 100MB)
2. Verify supported format (mp3, m4a, wav, webm, mp4)
3. Check disk space in UPLOAD_DIR

## License

Proprietary - Tarsyer Analytics Pvt Ltd
