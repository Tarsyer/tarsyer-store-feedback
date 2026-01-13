#!/usr/bin/env python3
"""
AI Analysis Worker Service
Polls for transcribed feedbacks and analyzes them using Qwen3 API
Extracts: summary, tone, products, issues, actions
"""
import os
import sys
import time
import json
import requests
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
QWEN_API_URL = os.getenv("QWEN_API_URL", "https://kwen.tarsyer.com/v1/chat/completions")
QWEN_API_KEY = os.getenv("QWEN_API_KEY", "Tarsyer-key-1")
QWEN_TARGET_SERVER = os.getenv("QWEN_TARGET_SERVER", "BK")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "10"))
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "1024"))


def log(message: str, level: str = "INFO"):
    """Simple logging with timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}", flush=True)


ANALYSIS_SYSTEM_PROMPT = """You are an expert retail analyst. Analyze store staff feedback and extract structured insights.

Your response MUST be valid JSON with exactly this structure:
{
    "summary": "Brief 2-3 sentence summary of the feedback",
    "tone": "positive" or "negative" or "neutral",
    "tone_score": 0.0 to 1.0 (0=very negative, 0.5=neutral, 1=very positive),
    "products": ["product1", "product2"],
    "issues": ["issue1", "issue2"],
    "actions": ["action1", "action2"],
    "keywords": ["keyword1", "keyword2"]
}

Guidelines:
- summary: Capture the main points in 2-3 sentences
- tone: Overall sentiment (positive/negative/neutral)
- tone_score: Numerical sentiment (0.0-1.0)
- products: Extract specific product names, brands, or categories mentioned
- issues: Problems, complaints, challenges mentioned by staff or customers
- actions: Suggested or needed actions, requests, improvements
- keywords: Key topics, themes, or important terms

If a category has no items, use an empty array [].
Always respond with valid JSON only, no additional text."""


ANALYSIS_USER_PROMPT = """Analyze this store staff feedback transcription and extract structured insights:

---
{transcription}
---

Remember to respond with valid JSON only."""


def analyze_with_qwen(transcription: str) -> tuple[bool, dict]:
    """
    Send transcription to Qwen3 API for analysis
    Returns (success, analysis_result_or_error)
    """
    if not transcription or len(transcription.strip()) < 10:
        return False, {"error": "Transcription too short for analysis"}
    
    try:
        payload = {
            "target_server": QWEN_TARGET_SERVER,
            "messages": [
                {
                    "role": "system",
                    "content": ANALYSIS_SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": ANALYSIS_USER_PROMPT.format(transcription=transcription[:4000])  # Limit input
                }
            ],
            "max_tokens": MAX_TOKENS,
            "temperature": 0.3  # Lower for more consistent structured output
        }
        
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": QWEN_API_KEY
        }
        
        response = requests.post(
            QWEN_API_URL,
            headers=headers,
            json=payload,
            timeout=120
        )
        
        if response.status_code != 200:
            return False, {"error": f"Qwen API error: {response.status_code} - {response.text}"}
        
        result = response.json()
        
        # Extract content from response
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        if not content:
            return False, {"error": "Empty response from Qwen API"}
        
        # Parse JSON from response
        # Handle potential markdown code blocks
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
        
        analysis = json.loads(content.strip())
        
        # Validate required fields
        required_fields = ["summary", "tone", "tone_score", "products", "issues", "actions", "keywords"]
        for field in required_fields:
            if field not in analysis:
                analysis[field] = [] if field in ["products", "issues", "actions", "keywords"] else ""
        
        # Normalize tone
        if analysis.get("tone") not in ["positive", "negative", "neutral"]:
            analysis["tone"] = "neutral"
        
        # Ensure tone_score is float
        try:
            analysis["tone_score"] = float(analysis.get("tone_score", 0.5))
            analysis["tone_score"] = max(0.0, min(1.0, analysis["tone_score"]))
        except:
            analysis["tone_score"] = 0.5
        
        return True, analysis
        
    except json.JSONDecodeError as e:
        log(f"JSON parse error: {e}", "ERROR")
        log(f"Raw content: {content[:500]}", "DEBUG")
        return False, {"error": f"Failed to parse Qwen response as JSON: {str(e)}"}
    except requests.exceptions.Timeout:
        return False, {"error": "Qwen API request timed out"}
    except Exception as e:
        return False, {"error": f"Qwen API error: {str(e)}"}


def get_transcribed_feedbacks(limit: int = 5) -> list:
    """Fetch feedbacks that have been transcribed but not analyzed"""
    try:
        response = requests.get(
            f"{API_BASE_URL}/api/v1/feedbacks",
            params={"status": "transcribed", "limit": limit},
            timeout=30
        )
        if response.status_code == 200:
            return response.json()
        return []
    except Exception as e:
        log(f"Failed to fetch transcribed feedbacks: {e}", "ERROR")
        return []


def update_analysis(feedback_id: str, analysis: dict) -> bool:
    """Update feedback with analysis result via API"""
    try:
        response = requests.patch(
            f"{API_BASE_URL}/api/internal/feedback/{feedback_id}/analysis",
            json=analysis,
            timeout=30
        )
        return response.status_code == 200
    except Exception as e:
        log(f"Failed to update analysis: {e}", "ERROR")
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


def process_feedback(feedback: dict):
    """Process a single feedback - analyze transcription"""
    feedback_id = feedback["id"]
    store_code = feedback.get("store_code", "UNKNOWN")
    transcription = feedback.get("transcription", "")
    
    log(f"Analyzing feedback {feedback_id} from store {store_code}")
    log(f"Transcription length: {len(transcription)} chars")
    
    if not transcription:
        log("No transcription found, skipping", "WARN")
        mark_error(feedback_id, "No transcription available for analysis")
        return
    
    # Analyze with Qwen
    success, result = analyze_with_qwen(transcription)
    
    if success:
        log(f"Analysis complete:")
        log(f"  Tone: {result.get('tone')} ({result.get('tone_score', 0):.2f})")
        log(f"  Products: {len(result.get('products', []))}")
        log(f"  Issues: {len(result.get('issues', []))}")
        log(f"  Actions: {len(result.get('actions', []))}")
        
        if update_analysis(feedback_id, result):
            log(f"✓ Updated feedback {feedback_id}")
        else:
            log(f"Failed to update feedback {feedback_id}", "ERROR")
    else:
        error_msg = result.get("error", "Unknown analysis error")
        log(f"Analysis failed: {error_msg}", "ERROR")
        mark_error(feedback_id, error_msg)


def check_qwen_api():
    """Verify Qwen API is reachable"""
    try:
        # Simple test request
        response = requests.post(
            QWEN_API_URL,
            headers={
                "Content-Type": "application/json",
                "X-API-Key": QWEN_API_KEY
            },
            json={
                "target_server": QWEN_TARGET_SERVER,
                "messages": [{"role": "user", "content": "Hi"}],
                "max_tokens": 10
            },
            timeout=30
        )
        if response.status_code == 200:
            log("✓ Qwen API connection verified")
            return True
        else:
            log(f"Qwen API returned status {response.status_code}", "WARN")
            return True  # Continue anyway, might work for real requests
    except Exception as e:
        log(f"Cannot reach Qwen API: {e}", "ERROR")
        return False


def main():
    """Main worker loop"""
    log("=" * 50)
    log("AI Analysis Worker Starting")
    log(f"API URL: {API_BASE_URL}")
    log(f"Qwen API URL: {QWEN_API_URL}")
    log(f"Target Server: {QWEN_TARGET_SERVER}")
    log("=" * 50)
    
    check_qwen_api()
    
    log(f"Polling every {POLL_INTERVAL} seconds...")
    
    while True:
        try:
            # Get transcribed feedbacks
            feedbacks = get_transcribed_feedbacks(limit=5)
            
            if feedbacks:
                log(f"Found {len(feedbacks)} feedbacks to analyze")
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
