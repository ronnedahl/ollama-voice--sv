"""Runtime configuration and constants for the voice AI backend."""

import os
from pathlib import Path

# Whisper (speech-to-text)
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "KBLab/kb-whisper-small")
WHISPER_DEVICE = "cuda"
WHISPER_COMPUTE_TYPE = "float16"

# Ollama (LLM)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")

# Piper (text-to-speech) — one model per supported language, picked at runtime
PIPER_MODEL_EN = os.getenv(
    "PIPER_MODEL_EN",
    "/app/voices/en_US-amy-medium.onnx",
)
PIPER_MODEL_SV = os.getenv(
    "PIPER_MODEL_SV",
    str(Path.home() / ".local/share/piper-voices/sv_SE-nst-medium.onnx"),
)
PIPER_MODELS = {"en": PIPER_MODEL_EN, "sv": PIPER_MODEL_SV}

# Language + prompts
LANGUAGE = os.getenv("LANGUAGE", "sv")
SYSTEM_PROMPTS = {
    "sv": (
        "Du är en hjälpsam svensk AI-assistent. Du MÅSTE svara endast på svenska, "
        "oavsett vilket språk som använts i tidigare meddelanden i den här konversationen. "
        "Var koncis och tydlig."
    ),
    "en": (
        "You are a helpful AI assistant. You MUST respond only in English, "
        "regardless of the language used in any earlier messages in this conversation. "
        "Be concise and clear."
    ),
}


def get_system_prompt(language: str) -> str:
    """Return the system prompt for the given language code."""
    if language not in SYSTEM_PROMPTS:
        raise ValueError(f"No system prompt configured for language {language!r}")
    return SYSTEM_PROMPTS[language]

# Music
MUSIC_DIR = os.getenv("MUSIC_DIR", str(Path.home() / "Music"))

# Upload limits
MAX_AUDIO_SIZE_MB = 10

# Voice activity detection
VAD_AGGRESSIVENESS = 3  # 0-3, higher = more aggressive filtering
VAD_SAMPLE_RATE = 16000  # WebRTC VAD requires 8000, 16000, 32000, or 48000
VAD_FRAME_DURATION_MS = 30  # 10, 20, or 30 ms
SILENCE_THRESHOLD_MS = 600  # silence duration before speech is considered ended
