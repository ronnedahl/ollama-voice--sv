"""Text-to-speech via the Piper CLI."""

import re
import subprocess
import tempfile
from pathlib import Path

from config import PIPER_MODEL


def generate_tts_audio(text: str) -> bytes:
    """Synthesize speech from text and return WAV bytes.

    Returns an empty bytes object when the input contains no word characters,
    since Piper crashes with "# channels not specified" if no audio is produced.
    """
    if not re.search(r"\w", text):
        return b""

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        output_path = tmp.name

    try:
        result = subprocess.run(
            ["piper", "--model", PIPER_MODEL, "--output_file", output_path],
            input=text,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Piper TTS failed: {result.stderr}")

        with open(output_path, "rb") as f:
            return f.read()
    finally:
        Path(output_path).unlink(missing_ok=True)
