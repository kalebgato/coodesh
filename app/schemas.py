from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ProcessingStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    SENT = "sent"
    FAILED = "failed"


class WebhookPayload(BaseModel):
    user_id: str = Field(min_length=3, max_length=64)
    message: str = Field(min_length=1, max_length=2000)


class EnqueueResponse(BaseModel):
    message_id: str
    status: ProcessingStatus


class MessageStatusResponse(BaseModel):
    message_id: str
    status: ProcessingStatus
    created_at: datetime
    updated_at: datetime
    error: Optional[str] = None


class MessageRecord(BaseModel):
    message_id: str
    user_id: str
    message: str
    status: ProcessingStatus
    created_at: datetime
    updated_at: datetime
    error: Optional[str] = None


class OutboundMessage(BaseModel):
    message_id: str
    user_id: str
    reply: str
    sent_at: datetime


class WebhookEvent(BaseModel):
    message_id: str
    user_id: str
    message: str
    received_at: datetime


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
