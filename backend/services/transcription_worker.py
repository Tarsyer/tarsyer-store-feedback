#!/usr/bin/env python3
"""
Transcription Worker Service
Polls for pending feedbacks and transcribes audio using whisper.cpp
"""
import os
import sys
import time
import subprocess
import tempfile
import requests
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/data/uploads")
WHISPER_CLI = os.getenv("WHISPER_CLI", "/opt/whisper.cpp/build/bin/whisper-cli")
MODEL_PATH = os.getenv("WHISPER_MODEL", "/opt/whisper.cpp/models/ggml-medium.bin")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "10"))  # seconds
LANGUAGE = os.getenv("WHISPER_LANG", "hi")  # Hindi default, use 'en' for English

# Audio extensions supported
AUDIO_EXTENSIONS = {'.mp3', '.mp4', '.mpeg', '.mpga', '.m4a', '.wav', '.webm', '.ogg', '.flac', '.aac'}


def log(message: str, level: str = "INFO"):
    """Simple logging with timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}", flush=True)


def convert_to_wav(input_path: str, output_path: str) -> bool:
    """Convert audio to 16kHz mono WAV for whisper"""
    try:
        subprocess.run(
            [
                "ffmpeg", "-i", input_path,
                "-ar", "16000",  # 16kHz sample rate
                "-ac", "1",      # Mono
                "-c:a", "pcm_s16le",  # 16-bit PCM
                output_path,
                "-y"  # Overwrite
            ],
            capture_output=True,
            check=True
        )
        return True
    except subprocess.CalledProcessError as e:
        log(f"FFmpeg conversion failed: {e.stderr.decode()}", "ERROR")
        return False


def transcribe_audio(audio_path: str) -> tuple[bool, str]:
    """
    Transcribe audio file using whisper.cpp
    Returns (success, transcription_or_error)
    """
    # Check if file exists
    if not os.path.exists(audio_path):
        return False, f"Audio file not found: {audio_path}"
    
    # Create temp WAV file
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        temp_wav = tmp.name
    
    try:
        log(f"Converting to WAV: {os.path.basename(audio_path)}")
        if not convert_to_wav(audio_path, temp_wav):
            return False, "Failed to convert audio to WAV"
        
        log(f"Running whisper transcription (lang={LANGUAGE})")
        result = subprocess.run(
            [
                WHISPER_CLI,
                "-m", MODEL_PATH,
                "-f", temp_wav,
                "-nt",  # No timestamps
                "-l", LANGUAGE,
                "-bs", "5",  # Beam size
                "--max-context", "0",
                "--entropy-thold", "2.8",
                "-tr"  # Translate to English (optional, remove if you want original language)
            ],
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout
        )
        
        if result.returncode != 0:
            return False, f"Whisper failed: {result.stderr}"
        
        transcription = result.stdout.strip()
        if not transcription:
            return False, "Empty transcription result"
        
        return True, transcription
        
    except subprocess.TimeoutExpired:
        return False, "Transcription timed out"
    except Exception as e:
        return False, f"Transcription error: {str(e)}"
    finally:
        # Clean up temp file
        if os.path.exists(temp_wav):
            os.unlink(temp_wav)


def update_transcription(feedback_id: str, transcription: str) -> bool:
    """Update feedback with transcription via API"""
    try:
        response = requests.patch(
            f"{API_BASE_URL}/api/internal/feedback/{feedback_id}/transcription",
            data={"transcription": transcription},
            timeout=30
        )
        return response.status_code == 200
    except Exception as e:
        log(f"Failed to update transcription: {e}", "ERROR")
        return False


def mark_error(feedback_id: str, error_message: str) -> bool:
    """Mark feedback as errored via API"""
    try:
        response = requests.patch(
            f"{API_BASE_URL}/api/internal/feedback/{feedback_id}/error",
            data={"error_message": error_message},
            timeout=30
        )
        return response.status_code == 200
    except Exception as e:
        log(f"Failed to mark error: {e}", "ERROR")
        return False


def get_pending_feedbacks(limit: int = 5) -> list:
    """Fetch pending feedbacks from API"""
    try:
        response = requests.get(
            f"{API_BASE_URL}/api/internal/pending",
            params={"limit": limit},
            timeout=30
        )
        if response.status_code == 200:
            return response.json()
        return []
    except Exception as e:
        log(f"Failed to fetch pending feedbacks: {e}", "ERROR")
        return []


def process_feedback(feedback: dict):
    """Process a single feedback - transcribe and update"""
    feedback_id = feedback["id"]
    store_code = feedback.get("store_code", "UNKNOWN")
    filename = feedback.get("media_filename") or os.path.basename(feedback.get("media_url", ""))
    
    log(f"Processing feedback {feedback_id} from store {store_code}")
    
    # Determine audio file path
    audio_path = os.path.join(UPLOAD_DIR, filename)
    
    # Transcribe
    success, result = transcribe_audio(audio_path)
    
    if success:
        log(f"Transcription complete ({len(result)} chars)")
        if update_transcription(feedback_id, result):
            log(f"✓ Updated feedback {feedback_id}")
        else:
            log(f"Failed to update feedback {feedback_id}", "ERROR")
    else:
        log(f"Transcription failed: {result}", "ERROR")
        mark_error(feedback_id, result)


def check_dependencies():
    """Verify required tools are available"""
    # Check whisper-cli
    if not os.path.exists(WHISPER_CLI):
        log(f"whisper-cli not found at {WHISPER_CLI}", "ERROR")
        log("Please set WHISPER_CLI environment variable", "ERROR")
        return False
    
    # Check model
    if not os.path.exists(MODEL_PATH):
        log(f"Whisper model not found at {MODEL_PATH}", "ERROR")
        log("Please set WHISPER_MODEL environment variable", "ERROR")
        return False
    
    # Check ffmpeg
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
    except:
        log("ffmpeg not found in PATH", "ERROR")
        return False
    
    log("✓ All dependencies verified")
    return True


def main():
    """Main worker loop"""
    log("=" * 50)
    log("Transcription Worker Starting")
    log(f"API URL: {API_BASE_URL}")
    log(f"Upload Dir: {UPLOAD_DIR}")
    log(f"Whisper CLI: {WHISPER_CLI}")
    log(f"Model: {MODEL_PATH}")
    log(f"Language: {LANGUAGE}")
    log("=" * 50)
    
    if not check_dependencies():
        sys.exit(1)
    
    log(f"Polling every {POLL_INTERVAL} seconds...")
    
    while True:
        try:
            # Get pending feedbacks
            feedbacks = get_pending_feedbacks(limit=5)
            
            if feedbacks:
                log(f"Found {len(feedbacks)} pending feedbacks")
                for feedback in feedbacks:
                    process_feedback(feedback)
            
            time.sleep(POLL_INTERVAL)
            
        except KeyboardInterrupt:
            log("Shutting down...")
            break
        except Exception as e:
            log(f"Worker error: {e}", "ERROR")
            time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
