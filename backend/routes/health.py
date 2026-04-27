"""Health and root endpoints."""

from fastapi import APIRouter

from config import OLLAMA_MODEL, PIPER_MODELS, WHISPER_MODEL

router = APIRouter(tags=["health"])


@router.get("/")
async def root():
    return {
        "status": "ok",
        "service": "Local Voice AI Assistant",
        "endpoints": ["/api/transcribe", "/api/chat", "/api/tts"],
    }


@router.get("/health")
async def health():
    return {
        "status": "healthy",
        "whisper_model": WHISPER_MODEL,
        "ollama_model": OLLAMA_MODEL,
        "tts_models": PIPER_MODELS,
    }
