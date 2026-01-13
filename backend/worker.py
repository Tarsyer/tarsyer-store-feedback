#!/usr/bin/env python3
"""
Background Worker for Store Feedback System
Processes pending transcriptions and LLM analyses

Run with: python worker.py
Or with PM2: pm2 start worker.py --interpreter python3 --name feedback-worker
"""
import os
import sys
import asyncio
import subprocess
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple

import httpx
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId

# Configuration from environment
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "store_feedback")
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/data/uploads")

# Whisper configuration
WHISPER_CLI = os.getenv("WHISPER_CLI", os.path.expanduser("~/whisper.cpp/build/bin/whisper-cli"))
WHISPER_MODEL = os.getenv("WHISPER_MODEL", os.path.expanduser("~/whisper.cpp/models/ggml-medium.bin"))
WHISPER_LANGUAGE = os.getenv("WHISPER_LANGUAGE", "hi")  # Hindi

# Qwen3 API configuration
QWEN_API_URL = os.getenv("QWEN_API_URL", "https://kwen.tarsyer.com/v1/chat/completions")
QWEN_API_KEY = os.getenv("QWEN_API_KEY", "Tarsyer-key-1")
QWEN_TARGET_SERVER = os.getenv("QWEN_TARGET_SERVER", "BK")

# Worker settings
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "30"))  # seconds
MAX_CONCURRENT = int(os.getenv("MAX_CONCURRENT", "2"))

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# MongoDB client
db_client: Optional[AsyncIOMotorClient] = None


# ============ LLM Prompt ============

ANALYSIS_PROMPT = """You are an AI assistant analyzing retail store staff feedback transcriptions from Bata stores in India.
The transcriptions are translated from Hindi to English.

Extract the following information in a structured JSON format:

1. summary: A brief 1-2 sentence summary of the feedback (in English)
2. tone: Overall tone - must be exactly one of: "positive", "negative", "neutral"
3. tone_score: Confidence score from 0 to 1 (e.g., 0.85 for strongly positive)
4. products: List of product names or categories mentioned (shoes, sandals, school shoes, etc.) - max 5
5. issues: List of problems or complaints mentioned (stock issues, display problems, customer complaints, etc.) - max 5
6. actions: List of suggested or required actions (restock, training, maintenance, etc.) - max 5
7. keywords: Key topic words for categorization - max 10

Respond ONLY with valid JSON, no other text. Example:
{
    "summary": "Staff reports good sales of school shoes but low stock on sandals. Customer asked for specific brand.",
    "tone": "neutral",
    "tone_score": 0.6,
    "products": ["school shoes", "sandals", "running shoes"],
    "issues": ["low stock on sandals", "display needs reorganizing"],
    "actions": ["restock sandals", "update display"],
    "keywords": ["stock", "display", "school shoes", "sales", "customer request"]
}"""


# ============ Transcription ============

async def transcribe_audio(audio_path: str) -> Tuple[bool, str]:
    """
    Transcribe audio file using whisper.cpp
    Returns: (success, transcription_or_error)
    """
    audio_path = Path(audio_path)
    temp_wav = None
    
    try:
        logger.info(f"Transcribing: {audio_path.name}")
        
        # Check if files exist
        if not audio_path.exists():
            return False, f"Audio file not found: {audio_path}"
        
        if not Path(WHISPER_CLI).exists():
            return False, f"Whisper CLI not found: {WHISPER_CLI}"
        
        if not Path(WHISPER_MODEL).exists():
            return False, f"Whisper model not found: {WHISPER_MODEL}"
        
        # Convert to WAV (16kHz mono) for whisper
        temp_wav = audio_path.parent / f"{audio_path.stem}_temp_{os.getpid()}.wav"
        
        logger.debug("Converting to WAV...")
        convert_proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-i", str(audio_path),
            "-ar", "16000", "-ac", "1",
            "-c:a", "pcm_s16le",
            str(temp_wav), "-y",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await convert_proc.communicate()
        
        if convert_proc.returncode != 0:
            return False, f"FFmpeg error: {stderr.decode()[:500]}"
        
        # Run whisper transcription
        logger.debug("Running whisper...")
        whisper_proc = await asyncio.create_subprocess_exec(
            WHISPER_CLI,
            "-m", WHISPER_MODEL,
            "-f", str(temp_wav),
            "-nt",  # No timestamps
            "-l", WHISPER_LANGUAGE,
            "-bs", "5",
            "--max-context", "0",
            "--entropy-thold", "2.8",
            "-tr",  # Translate to English
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await whisper_proc.communicate()
        
        if whisper_proc.returncode != 0:
            return False, f"Whisper error: {stderr.decode()[:500]}"
        
        transcription = stdout.decode().strip()
        logger.info(f"Transcription complete: {len(transcription)} chars")
        
        return True, transcription
        
    except Exception as e:
        logger.exception("Transcription error")
        return False, str(e)
        
    finally:
        if temp_wav and temp_wav.exists():
            try:
                temp_wav.unlink()
            except:
                pass


# ============ LLM Analysis ============

async def analyze_transcription(transcription: str) -> Tuple[bool, dict]:
    """
    Analyze transcription using Qwen3 API
    Returns: (success, analysis_dict_or_error)
    """
    if not transcription or len(transcription.strip()) < 10:
        return False, {"error": "Transcription too short"}
    
    try:
        payload = {
            "target_server": QWEN_TARGET_SERVER,
            "messages": [
                {"role": "system", "content": ANALYSIS_PROMPT},
                {"role": "user", "content": f"Analyze this store feedback transcription:\n\n{transcription}"}
            ],
            "max_tokens": 1000,
            "temperature": 0.3
        }
        
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": QWEN_API_KEY
        }
        
        logger.debug("Calling Qwen3 API...")
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(QWEN_API_URL, json=payload, headers=headers)
        
        if response.status_code != 200:
            return False, {"error": f"API error {response.status_code}: {response.text[:200]}"}
        
        result = response.json()
        
        # Extract content from response
        content = ""
        if "choices" in result and len(result["choices"]) > 0:
            content = result["choices"][0].get("message", {}).get("content", "")
        elif "content" in result:
            content = result["content"]
        
        if not content:
            return False, {"error": "Empty API response"}
        
        # Parse JSON from response
        analysis = parse_json_response(content)
        if not analysis:
            return False, {"error": f"Failed to parse JSON: {content[:200]}"}
        
        # Validate and normalize
        analysis = normalize_analysis(analysis)
        
        logger.info(f"Analysis complete: tone={analysis.get('tone')}")
        return True, analysis
        
    except httpx.TimeoutException:
        return False, {"error": "API timeout"}
    except Exception as e:
        logger.exception("Analysis error")
        return False, {"error": str(e)}


def parse_json_response(content: str) -> Optional[dict]:
    """Parse JSON from API response, handling markdown blocks"""
    content = content.strip()
    
    # Remove markdown code blocks
    if content.startswith("```json"):
        content = content[7:]
    elif content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]
    
    content = content.strip()
    
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # Try to find JSON object
        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(content[start:end])
            except:
                pass
    return None


def normalize_analysis(analysis: dict) -> dict:
    """Normalize and validate analysis output"""
    tone = analysis.get("tone", "neutral").lower()
    if tone not in ["positive", "negative", "neutral"]:
        tone = "neutral"
    
    return {
        "summary": str(analysis.get("summary", ""))[:500],
        "tone": tone,
        "tone_score": min(1.0, max(0.0, float(analysis.get("tone_score", 0.5)))),
        "products": [str(p)[:100] for p in analysis.get("products", [])][:5],
        "issues": [str(i)[:200] for i in analysis.get("issues", [])][:5],
        "actions": [str(a)[:200] for a in analysis.get("actions", [])][:5],
        "keywords": [str(k)[:50] for k in analysis.get("keywords", [])][:10]
    }


# ============ Worker Loop ============

async def process_pending():
    """Process all pending feedbacks"""
    db = db_client[DB_NAME]
    
    # Process pending transcriptions
    pending_transcription = await db.feedbacks.find(
        {"status": "pending"}
    ).limit(MAX_CONCURRENT).to_list(length=MAX_CONCURRENT)
    
    for doc in pending_transcription:
        feedback_id = doc["_id"]
        filename = doc.get("media_filename", "")
        filepath = Path(UPLOAD_DIR) / filename
        
        logger.info(f"Processing transcription for {feedback_id}")
        
        # Mark as processing
        await db.feedbacks.update_one(
            {"_id": feedback_id},
            {"$set": {"status": "transcribing", "updated_at": datetime.utcnow()}}
        )
        
        success, result = await transcribe_audio(str(filepath))
        
        if success:
            await db.feedbacks.update_one(
                {"_id": feedback_id},
                {
                    "$set": {
                        "transcription": result,
                        "status": "transcribed",
                        "updated_at": datetime.utcnow()
                    }
                }
            )
        else:
            await db.feedbacks.update_one(
                {"_id": feedback_id},
                {
                    "$set": {
                        "status": "error",
                        "error_message": f"Transcription failed: {result}",
                        "updated_at": datetime.utcnow()
                    }
                }
            )
    
    # Process pending analysis (transcribed but not analyzed)
    pending_analysis = await db.feedbacks.find(
        {"status": "transcribed", "transcription": {"$exists": True, "$ne": None}}
    ).limit(MAX_CONCURRENT).to_list(length=MAX_CONCURRENT)
    
    for doc in pending_analysis:
        feedback_id = doc["_id"]
        transcription = doc.get("transcription", "")
        
        logger.info(f"Processing analysis for {feedback_id}")
        
        # Mark as analyzing
        await db.feedbacks.update_one(
            {"_id": feedback_id},
            {"$set": {"status": "analyzing", "updated_at": datetime.utcnow()}}
        )
        
        success, result = await analyze_transcription(transcription)
        
        if success:
            await db.feedbacks.update_one(
                {"_id": feedback_id},
                {
                    "$set": {
                        "analysis": result,
                        "status": "completed",
                        "updated_at": datetime.utcnow()
                    }
                }
            )
        else:
            await db.feedbacks.update_one(
                {"_id": feedback_id},
                {
                    "$set": {
                        "status": "error",
                        "error_message": f"Analysis failed: {result.get('error', 'Unknown')}",
                        "updated_at": datetime.utcnow()
                    }
                }
            )


async def main():
    """Main worker loop"""
    global db_client
    
    logger.info("Starting Store Feedback Worker...")
    logger.info(f"MongoDB: {MONGO_URI}")
    logger.info(f"Upload Dir: {UPLOAD_DIR}")
    logger.info(f"Whisper CLI: {WHISPER_CLI}")
    logger.info(f"Poll Interval: {POLL_INTERVAL}s")
    
    # Connect to MongoDB
    db_client = AsyncIOMotorClient(MONGO_URI)
    
    # Verify connection
    try:
        await db_client.admin.command('ping')
        logger.info("✓ Connected to MongoDB")
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        sys.exit(1)
    
    # Check whisper availability
    if Path(WHISPER_CLI).exists() and Path(WHISPER_MODEL).exists():
        logger.info("✓ Whisper.cpp ready")
    else:
        logger.warning("⚠ Whisper.cpp not found - transcription will fail")
    
    # Main loop
    logger.info("Worker running. Press Ctrl+C to stop.")
    
    try:
        while True:
            try:
                await process_pending()
            except Exception as e:
                logger.error(f"Error in processing loop: {e}")
            
            await asyncio.sleep(POLL_INTERVAL)
    
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        db_client.close()


if __name__ == "__main__":
    asyncio.run(main())
