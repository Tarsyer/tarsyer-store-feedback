"""
Transcription service using whisper.cpp
Adapted from audio-service.py for server-side processing
"""
import os
import subprocess
import asyncio
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple

from app.core.config import get_settings
from app.services.database import Database
from app.models.schemas import ProcessingStatus

logger = logging.getLogger(__name__)
settings = get_settings()


class TranscriptionService:
    """Service for transcribing audio files using whisper.cpp"""
    
    @staticmethod
    def check_dependencies() -> Tuple[bool, str]:
        """Check if whisper.cpp and model are available"""
        if not os.path.exists(settings.WHISPER_CLI_PATH):
            return False, f"whisper-cli not found at {settings.WHISPER_CLI_PATH}"
        
        if not os.path.exists(settings.WHISPER_MODEL_PATH):
            return False, f"Whisper model not found at {settings.WHISPER_MODEL_PATH}"
        
        return True, "OK"
    
    @staticmethod
    async def transcribe_file(audio_path: str) -> Tuple[bool, str]:
        """
        Transcribe a single audio file using whisper-cli
        
        Args:
            audio_path: Path to the audio file
            
        Returns:
            Tuple of (success, transcription_or_error)
        """
        audio_path = Path(audio_path)
        temp_wav = None
        
        try:
            logger.info(f"Starting transcription: {audio_path.name}")
            
            # Convert to WAV format (16kHz mono) for whisper
            temp_wav = audio_path.parent / f"{audio_path.stem}_temp_{os.getpid()}.wav"
            
            logger.debug("Converting to WAV format...")
            
            # Run ffmpeg conversion
            convert_process = await asyncio.create_subprocess_exec(
                "ffmpeg", "-i", str(audio_path),
                "-ar", "16000", "-ac", "1",
                "-c:a", "pcm_s16le",
                str(temp_wav), "-y",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            _, stderr = await convert_process.communicate()
            
            if convert_process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown ffmpeg error"
                logger.error(f"FFmpeg conversion failed: {error_msg}")
                return False, f"Audio conversion failed: {error_msg}"
            
            logger.debug("Running whisper transcription...")
            
            # Run whisper transcription
            # Using same parameters as audio-service.py
            whisper_process = await asyncio.create_subprocess_exec(
                settings.WHISPER_CLI_PATH,
                "-m", settings.WHISPER_MODEL_PATH,
                "-f", str(temp_wav),
                "-nt",  # No timestamps
                "-l", settings.WHISPER_LANGUAGE,
                "-bs", "5",  # Beam size
                "--max-context", "0",
                "--entropy-thold", "2.8",
                "-tr",  # Translate to English
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await whisper_process.communicate()
            
            if whisper_process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown whisper error"
                logger.error(f"Whisper transcription failed: {error_msg}")
                return False, f"Transcription failed: {error_msg}"
            
            transcription = stdout.decode().strip()
            logger.info(f"Transcription completed: {len(transcription)} characters")
            
            return True, transcription
            
        except Exception as e:
            logger.exception(f"Unexpected error transcribing {audio_path.name}")
            return False, f"Transcription error: {str(e)}"
            
        finally:
            # Clean up temp file
            if temp_wav and temp_wav.exists():
                try:
                    temp_wav.unlink()
                except Exception as e:
                    logger.warning(f"Failed to delete temp file: {e}")
    
    @staticmethod
    async def get_audio_duration(audio_path: str) -> Optional[float]:
        """Get audio duration in seconds using ffprobe"""
        try:
            process = await asyncio.create_subprocess_exec(
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(audio_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, _ = await process.communicate()
            
            if process.returncode == 0:
                return float(stdout.decode().strip())
        except Exception as e:
            logger.warning(f"Could not get audio duration: {e}")
        
        return None


async def process_pending_transcriptions():
    """
    Background worker to process pending transcriptions
    Called periodically by the scheduler
    """
    db = Database.get_db()
    
    # Find pending transcriptions
    pending = await db.feedbacks.find({
        "transcription_status": ProcessingStatus.PENDING.value
    }).limit(settings.MAX_CONCURRENT_TRANSCRIPTIONS).to_list(length=None)
    
    if not pending:
        return
    
    logger.info(f"Processing {len(pending)} pending transcriptions")
    
    for feedback in pending:
        feedback_id = feedback["_id"]
        audio_path = feedback.get("audio_url", "")
        
        # Convert URL path to file system path
        if audio_path.startswith("/uploads/"):
            file_path = Path(settings.UPLOAD_DIR) / audio_path.replace("/uploads/", "")
        else:
            file_path = Path(audio_path)
        
        if not file_path.exists():
            logger.error(f"Audio file not found: {file_path}")
            await db.feedbacks.update_one(
                {"_id": feedback_id},
                {
                    "$set": {
                        "transcription_status": ProcessingStatus.FAILED.value,
                        "transcription_error": f"Audio file not found: {file_path}"
                    }
                }
            )
            continue
        
        # Mark as processing
        await db.feedbacks.update_one(
            {"_id": feedback_id},
            {"$set": {"transcription_status": ProcessingStatus.PROCESSING.value}}
        )
        
        # Transcribe
        success, result = await TranscriptionService.transcribe_file(str(file_path))
        
        if success:
            # Get audio duration
            duration = await TranscriptionService.get_audio_duration(str(file_path))
            
            await db.feedbacks.update_one(
                {"_id": feedback_id},
                {
                    "$set": {
                        "transcription": result,
                        "transcription_status": ProcessingStatus.COMPLETED.value,
                        "transcribed_at": datetime.utcnow(),
                        "audio_duration_seconds": duration
                    }
                }
            )
            logger.info(f"Transcription completed for feedback {feedback_id}")
        else:
            await db.feedbacks.update_one(
                {"_id": feedback_id},
                {
                    "$set": {
                        "transcription_status": ProcessingStatus.FAILED.value,
                        "transcription_error": result
                    }
                }
            )
            logger.error(f"Transcription failed for feedback {feedback_id}: {result}")
