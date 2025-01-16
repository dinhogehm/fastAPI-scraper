from pydantic import BaseModel, HttpUrl
from typing import Optional, List
from enum import Enum
from datetime import datetime

class ProcessingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class ScrapeRequest(BaseModel):
    url: HttpUrl
    callback_url: Optional[HttpUrl] = None

class ScrapeResult(BaseModel):
    id: str
    url: HttpUrl
    status: ProcessingStatus
    content: Optional[str] = None
    links: Optional[List[str]] = None
    error: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

class StatusResponse(BaseModel):
    id: str
    status: ProcessingStatus
    message: Optional[str] = None
    content: Optional[str] = None
    links: Optional[List[str]] = None
    error: Optional[str] = None
