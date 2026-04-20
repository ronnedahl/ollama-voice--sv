"""Text-to-speech via the Piper CLI."""

import re
import subprocess
import tempfile
from pathlib import Path

from config import PIPER_MODEL


def _clean_text_for_tts(text: str) -> str:
    """Strip markdown so Piper doesn't read '**' as 'asterisk asterisk'."""
    # Fenced code blocks first (they can contain other markdown)
    text = re.sub(r"```[\s\S]*?```", " ", text)
    # Inline code: keep the text, drop the backticks
    text = re.sub(r"`([^`]*)`", r"\1", text)
    # Bold/italic markers (**, __, *, _)
    text = re.sub(r"\*+", "", text)
    text = re.sub(r"_+", "", text)
    # Markdown headers at line start: "## Title" -> "Title"
    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)
    # List bullets at line start: "- item", "* item", "+ item"
    text = re.sub(r"^\s*[-+*]\s+", "", text, flags=re.MULTILINE)
    # Link syntax: "[text](url)" -> "text"
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def generate_tts_audio(text: str) -> bytes:
    """Synthesize speech from text and return WAV bytes.

    Returns an empty bytes object when the input contains no word characters,
    since Piper crashes with "# channels not specified" if no audio is produced.
    """
    cleaned = _clean_text_for_tts(text)
    if not re.search(r"\w", cleaned):
        return b""

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        output_path = tmp.name

    try:
        result = subprocess.run(
            ["piper", "--model", PIPER_MODEL, "--output_file", output_path],
            input=cleaned,
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
