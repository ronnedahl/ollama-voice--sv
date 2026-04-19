"""Audio transcription endpoint."""

import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from config import LANGUAGE, MAX_AUDIO_SIZE_MB
from schemas import TranscribeResponse
from services.whisper import get_whisper_model

router = APIRouter(prefix="/api", tags=["transcribe"])


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe(audio: UploadFile = File(...)):
    """Transcribe an uploaded audio file."""
    contents = await audio.read()
    size_mb = len(contents) / (1024 * 1024)
    if size_mb > MAX_AUDIO_SIZE_MB:
        raise HTTPException(
            status_code=413,
            detail=f"Audio file too large. Max {MAX_AUDIO_SIZE_MB}MB",
        )

    suffix = Path(audio.filename).suffix if audio.filename else ".webm"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        model = get_whisper_model()
        segments, info = model.transcribe(
            tmp_path,
            language=LANGUAGE,
            beam_size=5,
            vad_filter=True,
        )

        text_parts = [segment.text.strip() for segment in segments]
        full_text = " ".join(text_parts)

        return TranscribeResponse(
            text=full_text,
            language=info.language,
            confidence=info.language_probability,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {e}")

    finally:
        Path(tmp_path).unlink(missing_ok=True)
