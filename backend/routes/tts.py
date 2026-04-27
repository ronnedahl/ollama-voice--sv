"""Text-to-speech REST endpoint (returns a WAV file)."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from schemas import TTSRequest
from services.tts import generate_tts_audio

router = APIRouter(prefix="/api", tags=["tts"])


@router.post("/tts")
async def text_to_speech(request: TTSRequest):
    """Convert text to speech using Piper TTS (current language voice)."""
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    try:
        audio_bytes = generate_tts_audio(request.text)
    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail="Piper not found. Install with: pipx install piper-tts",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS failed: {e}")

    if not audio_bytes:
        raise HTTPException(status_code=400, detail="No speech generated from input")

    return Response(content=audio_bytes, media_type="audio/wav")
