"""
LLM Analysis service using Qwen3 API
Extracts tone, products, issues, and actions from transcriptions
"""
import httpx
import json
import logging
from datetime import datetime
from typing import Tuple, Optional

from app.core.config import get_settings
from app.services.database import Database
from app.models.schemas import FeedbackAnalysis, ProcessingStatus, ToneType

logger = logging.getLogger(__name__)
settings = get_settings()

# System prompt for structured extraction
ANALYSIS_SYSTEM_PROMPT = """You are an AI assistant analyzing retail store staff feedback transcriptions.
Extract the following information in a structured JSON format:

1. summary: A brief 1-2 sentence summary of the feedback
2. tone: Overall tone - must be exactly one of: "positive", "negative", "neutral"
3. tone_score: Confidence score from 0 to 1 (e.g., 0.85 for strongly positive)
4. products: List of product names or categories mentioned (max 5)
5. issues: List of problems or complaints mentioned (max 5)
6. actions: List of suggested or required actions (max 5)
7. keywords: Key topic words for categorization (max 10)

Respond ONLY with valid JSON, no other text. Example:
{
    "summary": "Staff reports good sales of new shoes, but low stock on sandals",
    "tone": "neutral",
    "tone_score": 0.6,
    "products": ["running shoes", "sandals", "school shoes"],
    "issues": ["low stock on sandals", "display needs fixing"],
    "actions": ["restock sandals", "fix shoe display"],
    "keywords": ["stock", "display", "shoes", "sales"]
}"""


class LLMAnalysisService:
    """Service for analyzing transcriptions using Qwen3 API"""
    
    @staticmethod
    async def analyze_transcription(transcription: str) -> Tuple[bool, FeedbackAnalysis | str]:
        """
        Analyze a transcription using Qwen3 API
        
        Args:
            transcription: The transcribed text to analyze
            
        Returns:
            Tuple of (success, FeedbackAnalysis or error_message)
        """
        if not transcription or len(transcription.strip()) < 10:
            return False, "Transcription too short to analyze"
        
        try:
            # Prepare the API request
            payload = {
                "target_server": settings.QWEN_TARGET_SERVER,
                "messages": [
                    {
                        "role": "system",
                        "content": ANALYSIS_SYSTEM_PROMPT
                    },
                    {
                        "role": "user",
                        "content": f"Analyze this store feedback transcription:\n\n{transcription}"
                    }
                ],
                "max_tokens": settings.QWEN_MAX_TOKENS,
                "temperature": 0.3,  # Lower temperature for more consistent outputs
            }
            
            headers = {
                "Content-Type": "application/json",
                "X-API-Key": settings.QWEN_API_KEY
            }
            
            logger.debug(f"Calling Qwen3 API for analysis...")
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    settings.QWEN_API_URL,
                    json=payload,
                    headers=headers
                )
                
                if response.status_code != 200:
                    error_msg = f"API returned status {response.status_code}: {response.text}"
                    logger.error(error_msg)
                    return False, error_msg
                
                result = response.json()
            
            # Extract the content from the response
            content = ""
            if "choices" in result and len(result["choices"]) > 0:
                message = result["choices"][0].get("message", {})
                content = message.get("content", "")
            elif "content" in result:
                content = result["content"]
            
            if not content:
                return False, "Empty response from API"
            
            # Parse the JSON response
            analysis_data = LLMAnalysisService._parse_json_response(content)
            
            if analysis_data is None:
                return False, f"Failed to parse API response as JSON: {content[:200]}"
            
            # Create FeedbackAnalysis object
            analysis = FeedbackAnalysis(
                summary=analysis_data.get("summary", ""),
                tone=LLMAnalysisService._parse_tone(analysis_data.get("tone", "neutral")),
                tone_score=min(1.0, max(0.0, float(analysis_data.get("tone_score", 0.5)))),
                products=analysis_data.get("products", [])[:5],
                issues=analysis_data.get("issues", [])[:5],
                actions=analysis_data.get("actions", [])[:5],
                keywords=analysis_data.get("keywords", [])[:10]
            )
            
            logger.info(f"Analysis completed: tone={analysis.tone}, {len(analysis.products)} products, {len(analysis.issues)} issues")
            
            return True, analysis
            
        except httpx.TimeoutException:
            logger.error("Qwen3 API request timed out")
            return False, "API request timed out"
        except httpx.RequestError as e:
            logger.error(f"Qwen3 API request error: {e}")
            return False, f"API request error: {str(e)}"
        except Exception as e:
            logger.exception("Unexpected error during analysis")
            return False, f"Analysis error: {str(e)}"
    
    @staticmethod
    def _parse_json_response(content: str) -> Optional[dict]:
        """Parse JSON from API response, handling markdown code blocks"""
        content = content.strip()
        
        # Remove markdown code blocks if present
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
            # Try to find JSON object in the response
            start_idx = content.find("{")
            end_idx = content.rfind("}") + 1
            
            if start_idx >= 0 and end_idx > start_idx:
                try:
                    return json.loads(content[start_idx:end_idx])
                except json.JSONDecodeError:
                    pass
        
        return None
    
    @staticmethod
    def _parse_tone(tone_str: str) -> ToneType:
        """Parse tone string to ToneType enum"""
        tone_lower = tone_str.lower().strip()
        
        if "positive" in tone_lower:
            return ToneType.POSITIVE
        elif "negative" in tone_lower:
            return ToneType.NEGATIVE
        else:
            return ToneType.NEUTRAL


async def process_pending_analyses():
    """
    Background worker to process pending LLM analyses
    Called periodically by the scheduler
    """
    db = Database.get_db()
    
    # Find feedbacks that have completed transcription but pending analysis
    pending = await db.feedbacks.find({
        "transcription_status": ProcessingStatus.COMPLETED.value,
        "analysis_status": ProcessingStatus.PENDING.value,
        "transcription": {"$exists": True, "$ne": None}
    }).limit(5).to_list(length=None)
    
    if not pending:
        return
    
    logger.info(f"Processing {len(pending)} pending analyses")
    
    for feedback in pending:
        feedback_id = feedback["_id"]
        transcription = feedback.get("transcription", "")
        
        # Mark as processing
        await db.feedbacks.update_one(
            {"_id": feedback_id},
            {"$set": {"analysis_status": ProcessingStatus.PROCESSING.value}}
        )
        
        # Analyze
        success, result = await LLMAnalysisService.analyze_transcription(transcription)
        
        if success:
            await db.feedbacks.update_one(
                {"_id": feedback_id},
                {
                    "$set": {
                        "analysis": result.model_dump(),
                        "analysis_status": ProcessingStatus.COMPLETED.value,
                        "analyzed_at": datetime.utcnow()
                    }
                }
            )
            logger.info(f"Analysis completed for feedback {feedback_id}")
        else:
            await db.feedbacks.update_one(
                {"_id": feedback_id},
                {
                    "$set": {
                        "analysis_status": ProcessingStatus.FAILED.value,
                        "analysis_error": result
                    }
                }
            )
            logger.error(f"Analysis failed for feedback {feedback_id}: {result}")
