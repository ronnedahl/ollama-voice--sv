"""Voice activity detection and WAV assembly for streaming PCM audio."""

import io
import wave

import webrtcvad

from config import (
    SILENCE_THRESHOLD_MS,
    VAD_AGGRESSIVENESS,
    VAD_FRAME_DURATION_MS,
    VAD_SAMPLE_RATE,
)


class AudioBuffer:
    """Buffer for collecting PCM audio chunks and detecting speech boundaries."""

    def __init__(self):
        self.vad = webrtcvad.Vad(VAD_AGGRESSIVENESS)
        self.audio_chunks: list[bytes] = []
        self.sample_rate = VAD_SAMPLE_RATE
        self.frame_duration_ms = VAD_FRAME_DURATION_MS
        self.silence_frames = 0
        self.speech_detected = False
        self.frames_per_silence_threshold = SILENCE_THRESHOLD_MS // VAD_FRAME_DURATION_MS

    def add_chunk(self, pcm_data: bytes) -> str:
        """Add a PCM chunk and return 'speech', 'silence', or 'speech_ended'."""
        self.audio_chunks.append(pcm_data)

        frame_size = (self.sample_rate * self.frame_duration_ms // 1000) * 2  # 16-bit = 2 bytes
        if len(pcm_data) >= frame_size:
            frame = pcm_data[:frame_size]
            try:
                is_speech = self.vad.is_speech(frame, self.sample_rate)
            except Exception:
                is_speech = True  # Assume speech on error

            if is_speech:
                self.speech_detected = True
                self.silence_frames = 0
                return "speech"
            else:
                if self.speech_detected:
                    self.silence_frames += 1
                    if self.silence_frames >= self.frames_per_silence_threshold:
                        return "speech_ended"
                return "silence"

        return "silence"

    def get_wav_bytes(self) -> bytes:
        """Convert collected PCM chunks to WAV-format bytes."""
        pcm_data = b"".join(self.audio_chunks)

        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(pcm_data)

        wav_buffer.seek(0)
        return wav_buffer.read()

    def reset(self):
        """Clear buffered audio and reset speech tracking for a new recording."""
        self.audio_chunks = []
        self.silence_frames = 0
        self.speech_detected = False
