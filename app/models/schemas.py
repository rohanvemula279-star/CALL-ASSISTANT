"""Pydantic request/response schemas for the API."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class TranscribeRequest(BaseModel):
    """Request for transcribe endpoint (raw bytes handled separately as file)."""

    language: Optional[str] = Field(default=None, description="Source language hint, e.g. 'en'")


class TranscribeResponse(BaseModel):
    text: str
    language: Optional[str] = None
    duration: Optional[float] = None
    segments: Optional[list[dict]] = None


class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(system|user|assistant)$")
    content: str


class ChatRequest(BaseModel):
    call_id: Optional[str] = Field(default=None, description="Asterisk call identifier")
    caller: Optional[str] = Field(default=None, description="Caller phone number")
    message: str = Field(..., min_length=1)
    system_prompt: Optional[str] = None
    history: Optional[list[ChatMessage]] = None
    temperature: float = 0.7
    max_tokens: Optional[int] = None


class ChatResponse(BaseModel):
    call_id: Optional[str] = None
    reply: str
    model: str
    latency_ms: float


class SpeakRequest(BaseModel):
    text: str = Field(..., min_length=1)
    voice: Optional[str] = None
    speed: float = 1.0


class SpeakResponse(BaseModel):
    audio_path: str
    audio_url: str
    duration_estimate: float
    voice: str


class ConversationEntry(BaseModel):
    id: int
    call_id: Optional[str]
    role: str
    content: str
    created_at: datetime


class HealthResponse(BaseModel):
    status: str
    environment: str
    ollama: dict
    whisper: dict
    piper: dict
