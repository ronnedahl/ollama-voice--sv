"""Text-to-speech REST endpoint (returns a WAV file)."""

import subprocess
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from config import PIPER_MODEL
from schemas import TTSRequest

router = APIRouter(prefix="/api", tags=["tts"])


@router.post("/tts")
async def text_to_speech(request: TTSRequest):
    """Convert text to speech using Piper TTS CLI."""
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        output_path = tmp.name

    try:
        result = subprocess.run(
            [
                "piper",
                "--model", PIPER_MODEL,
                "--output_file", output_path,
            ],
            input=request.text,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=f"Piper TTS failed: {result.stderr}",
            )

        return FileResponse(
            output_path,
            media_type="audio/wav",
            filename="speech.wav",
            background=None,
        )

    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail="Piper not found. Install with: pipx install piper-tts",
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="TTS timed out")
    except Exception as e:
        Path(output_path).unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"TTS failed: {e}")
