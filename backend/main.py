from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any
import os
import logging
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from datetime import datetime

from database import get_db, Summary
from services import process_video_summary

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="YouTube Summarizer API",
    description="Backend API for YouTube video summarization service",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for request/response
class SummaryRequest(BaseModel):
    video_url: str
    mode: Optional[str] = "detailed"
    tone: Optional[str] = "simple"
    chunk_size: Optional[int] = 180

class SummaryResponse(BaseModel):
    video_id: str
    summary: Optional[str]
    status: str
    error: Optional[str] = None

async def process_summary_task(
    video_url: str,
    mode: str,
    tone: str,
    chunk_size: int,
    db: Session,
    summary_record: Summary
):
    """Background task to process video summary."""
    try:
        result = await process_video_summary(video_url, mode, tone, chunk_size)
        
        # Update database record
        summary_record.video_id = result["video_id"]
        summary_record.summary = result["summary"]
        summary_record.status = result["status"]
        summary_record.error = result["error"]
        summary_record.updated_at = datetime.utcnow()
        
        db.commit()
    
    except Exception as e:
        logger.error(f"Error in background task: {str(e)}")
        summary_record.status = "error"
        summary_record.error = str(e)
        summary_record.updated_at = datetime.utcnow()
        db.commit()

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "1.0.0"}

# Summary request endpoint
@app.post("/api/summarize", response_model=SummaryResponse)
async def create_summary(
    request: SummaryRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    try:
        # Create database record
        summary_record = Summary(
            video_url=request.video_url,
            status="pending",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(summary_record)
        db.commit()
        db.refresh(summary_record)
        
        # Add background task
        background_tasks.add_task(
            process_summary_task,
            request.video_url,
            request.mode,
            request.tone,
            request.chunk_size,
            db,
            summary_record
        )
        
        return {
            "video_id": summary_record.video_id,
            "summary": None,
            "status": "pending",
            "error": None
        }
    
    except Exception as e:
        logger.error(f"Error creating summary: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Get summary status endpoint
@app.get("/api/summary/{video_id}", response_model=SummaryResponse)
async def get_summary_status(video_id: str, db: Session = Depends(get_db)):
    try:
        summary = db.query(Summary).filter(Summary.video_id == video_id).first()
        
        if not summary:
            raise HTTPException(status_code=404, detail="Summary not found")
        
        return {
            "video_id": summary.video_id,
            "summary": summary.summary,
            "status": summary.status,
            "error": summary.error
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking summary status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 