"""Speech-to-text via faster-whisper."""

import tempfile
from pathlib import Path

from config import WHISPER_COMPUTE_TYPE, WHISPER_DEVICE, WHISPER_MODEL
from state import language_state

_whisper_model = None


def get_whisper_model():
    """Lazy-load the Whisper model on first use."""
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel

        print(f"Loading Whisper model '{WHISPER_MODEL}' on {WHISPER_DEVICE}...")
        _whisper_model = WhisperModel(
            WHISPER_MODEL,
            device=WHISPER_DEVICE,
            compute_type=WHISPER_COMPUTE_TYPE,
        )
        print("Whisper model loaded")
    return _whisper_model


def transcribe_audio_bytes(audio_bytes: bytes) -> tuple[str, float]:
    """Transcribe raw WAV bytes and return (text, language_probability)."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        model = get_whisper_model()
        # Hint Whisper with the currently-configured language. Auto-detect is
        # unreliable on short imperatives ("byt till engelska") and produces
        # phonetic gibberish that breaks command detection. Trade-off: switch
        # commands must be spoken in the current language.
        segments, info = model.transcribe(
            tmp_path,
            language=language_state.get(),
            beam_size=5,
            vad_filter=True,
        )

        text_parts = [segment.text.strip() for segment in segments]
        full_text = " ".join(text_parts)
        return full_text, info.language_probability
    finally:
        Path(tmp_path).unlink(missing_ok=True)
