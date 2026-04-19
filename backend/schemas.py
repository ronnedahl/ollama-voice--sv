"""Pydantic request/response models for the voice AI backend."""

from typing import Optional

from pydantic import BaseModel


class ChatRequest(BaseModel):
    text: str
    system_prompt: Optional[str] = None


class ChatResponse(BaseModel):
    response: str


class TranscribeResponse(BaseModel):
    text: str
    language: str
    confidence: float


class TTSRequest(BaseModel):
    text: str
