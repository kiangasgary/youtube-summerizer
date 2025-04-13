import re
from typing import Optional, Dict, Any
from youtube_transcript_api import YouTubeTranscriptApi
from model_manager import GoogleAIModelManager
import logging
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize AI model manager
model_manager = GoogleAIModelManager(os.getenv('GEMINI_API_KEY'))

def extract_video_id(url: str) -> Optional[str]:
    """Extract YouTube video ID from various URL formats."""
    patterns = [
        r'(?:v=|/v/|youtu\.be/|/embed/)([^&?/]+)',
        r'youtube.com/shorts/([^&?/]+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

async def get_transcript(video_id: str) -> str:
    """Get transcript for a YouTube video."""
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        transcript = transcript_list.find_transcript(['en', 'en-US', 'en-GB'])
        
        if not transcript:
            raise Exception("No English transcript available")
        
        transcript_data = transcript.fetch()
        return " ".join([entry['text'] for entry in transcript_data])
    
    except Exception as e:
        logger.error(f"Error fetching transcript: {str(e)}")
        raise

async def generate_summary(transcript: str, mode: str = "detailed", tone: str = "simple", chunk_size: int = 180) -> str:
    """Generate summary using AI model."""
    try:
        # Split transcript into chunks
        chunks = [transcript[i:i + chunk_size] for i in range(0, len(transcript), chunk_size)]
        all_summaries = []
        
        for chunk in chunks:
            tone_instruction = {
                'simple': "Use simple, everyday language",
                'technical': "Use technical, precise language",
                'beginner-friendly': "Explain concepts as if to a beginner"
            }[tone]
            
            prompt = f"""Analyze this part of the video transcript and create a {mode} summary.
            {tone_instruction} and focus on clarity and coherence.
            
            Transcript chunk:
            {chunk}"""
            
            try:
                summary = await model_manager.generate_content(prompt)
                if summary:
                    all_summaries.append(summary)
            except Exception as e:
                logger.error(f"Error processing chunk: {str(e)}")
                continue
        
        if not all_summaries:
            raise Exception("Failed to generate summary")
        
        return "\n\n".join(all_summaries)
    
    except Exception as e:
        logger.error(f"Error generating summary: {str(e)}")
        raise

async def process_video_summary(video_url: str, mode: str = "detailed", tone: str = "simple", chunk_size: int = 180) -> Dict[str, Any]:
    """Process a video URL and return a summary."""
    try:
        # Extract video ID
        video_id = extract_video_id(video_url)
        if not video_id:
            raise ValueError("Invalid YouTube URL")
        
        # Get transcript
        transcript = await get_transcript(video_id)
        
        # Generate summary
        summary = await generate_summary(transcript, mode, tone, chunk_size)
        
        return {
            "video_id": video_id,
            "summary": summary,
            "status": "completed",
            "error": None
        }
    
    except Exception as e:
        logger.error(f"Error processing video summary: {str(e)}")
        return {
            "video_id": video_id if 'video_id' in locals() else None,
            "summary": None,
            "status": "error",
            "error": str(e)
        } 