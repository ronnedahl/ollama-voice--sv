"""
Local Voice AI Assistant - FastAPI Backend

Endpoints:
- /api/transcribe: Speech-to-Text (faster-whisper)
- /api/chat: LLM responses (Ollama)
- /api/tts: Text-to-Speech (Piper TTS via CLI)
- /ws/chat: WebSocket for streaming LLM + TTS responses
- /ws/voice: WebSocket for full voice pipeline with VAD
"""

import asyncio
import base64
import re

import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from config import SYSTEM_PROMPT
from music import detect_play_command, detect_stop_command
from routes import chat as chat_route
from routes import health as health_route
from routes import music as music_route
from routes import transcribe as transcribe_route
from routes import tts as tts_route
from services import ollama
from services.tts import generate_tts_audio
from services.vad import AudioBuffer
from services.whisper import transcribe_audio_bytes
from state import music_library

app = FastAPI(
    title="Local Voice AI Assistant",
    description="Lokal Röst-AI Assistent",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_route.router)
app.include_router(music_route.router)
app.include_router(transcribe_route.router)
app.include_router(chat_route.router)
app.include_router(tts_route.router)


@app.on_event("startup")
async def startup_event():
    music_library.scan()


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """WebSocket endpoint for streaming LLM + TTS responses."""
    await websocket.accept()

    try:
        while True:
            data = await websocket.receive_json()

            if data.get("type") == "chat":
                text = data.get("text", "").strip()
                enable_tts = data.get("tts", True)  # TTS enabled by default

                if not text:
                    await websocket.send_json({"type": "error", "message": "Text cannot be empty"})
                    continue

                system_prompt = data.get("system_prompt") or SYSTEM_PROMPT
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text},
                ]

                try:
                    full_response = ""
                    sentence_buffer = ""

                    async for token in ollama.stream_chat(messages):
                        full_response += token
                        sentence_buffer += token

                        # Send token for live text display
                        await websocket.send_json({
                            "type": "llm_token",
                            "token": token,
                        })

                        # Check for sentence boundary and generate TTS
                        if enable_tts and re.search(r'[.!?]\s*$', sentence_buffer):
                            sentence = sentence_buffer.strip()
                            sentence_buffer = ""

                            if sentence:
                                try:
                                    audio_bytes = await asyncio.to_thread(
                                        generate_tts_audio, sentence
                                    )
                                    audio_base64 = base64.b64encode(audio_bytes).decode()
                                    await websocket.send_json({
                                        "type": "audio_chunk",
                                        "audio": audio_base64,
                                        "text": sentence,
                                    })
                                except Exception as e:
                                    await websocket.send_json({
                                        "type": "tts_error",
                                        "message": str(e),
                                    })

                    # Handle any remaining text in buffer
                    if enable_tts and sentence_buffer.strip():
                        try:
                            audio_bytes = await asyncio.to_thread(
                                generate_tts_audio, sentence_buffer.strip()
                            )
                            audio_base64 = base64.b64encode(audio_bytes).decode()
                            await websocket.send_json({
                                "type": "audio_chunk",
                                "audio": audio_base64,
                                "text": sentence_buffer.strip(),
                            })
                        except Exception as e:
                            await websocket.send_json({
                                "type": "tts_error",
                                "message": str(e),
                            })

                    await websocket.send_json({
                        "type": "llm_done",
                        "full_response": full_response,
                    })

                except httpx.ConnectError:
                    await websocket.send_json({"type": "error", "message": "Cannot connect to Ollama"})
                except Exception as e:
                    await websocket.send_json({"type": "error", "message": str(e)})

    except WebSocketDisconnect:
        pass


@app.websocket("/ws/voice")
async def websocket_voice(websocket: WebSocket):
    """
    Unified WebSocket endpoint for full voice pipeline with VAD.

    Protocol:
    - Client sends: {"type": "audio_chunk", "audio": base64_pcm_16khz_mono}
    - Client sends: {"type": "stop"} to force end recording
    - Server sends: {"type": "vad_state", "state": "listening"|"speech"|"processing"}
    - Server sends: {"type": "transcript", "text": "...", "confidence": 0.95}
    - Server sends: {"type": "llm_token", "token": "..."}
    - Server sends: {"type": "audio_chunk", "audio": base64_wav, "text": "..."}
    - Server sends: {"type": "done"}
    """
    await websocket.accept()
    audio_buffer = AudioBuffer()

    # Keepalive ping every 30 seconds to prevent timeout
    async def keepalive():
        while True:
            await asyncio.sleep(30)
            try:
                await websocket.send_json({"type": "ping"})
            except Exception:
                break

    keepalive_task = asyncio.create_task(keepalive())

    async def process_speech():
        """Process the recorded speech through the full pipeline."""
        await websocket.send_json({"type": "vad_state", "state": "processing"})

        # Get WAV audio
        wav_bytes = audio_buffer.get_wav_bytes()

        # Transcribe
        try:
            text, confidence = await asyncio.to_thread(transcribe_audio_bytes, wav_bytes)
        except Exception as e:
            await websocket.send_json({"type": "error", "message": f"Transcription failed: {e}"})
            return

        if not text.strip():
            audio_buffer.reset()
            await websocket.send_json({"type": "vad_state", "state": "listening"})
            return

        await websocket.send_json({
            "type": "transcript",
            "text": text,
            "confidence": confidence,
        })

        # Check for music commands before invoking LLM
        if detect_stop_command(text):
            await websocket.send_json({"type": "stop_music"})
            audio_buffer.reset()
            return

        play_query = detect_play_command(text)
        if play_query:
            track = music_library.search(play_query)
            if track:
                await websocket.send_json({
                    "type": "play_song",
                    "track": track.to_dict(),
                    "url": f"/api/music/file/{track.id}",
                })
            else:
                await websocket.send_json({
                    "type": "music_not_found",
                    "query": play_query,
                })
            audio_buffer.reset()
            return

        # LLM + TTS streaming
        system_prompt = SYSTEM_PROMPT
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ]

        try:
            full_response = ""
            sentence_buffer = ""

            async for token in ollama.stream_chat(messages):
                full_response += token
                sentence_buffer += token

                await websocket.send_json({
                    "type": "llm_token",
                    "token": token,
                })

                # Generate TTS for completed sentences
                if re.search(r'[.!?]\s*$', sentence_buffer):
                    sentence = sentence_buffer.strip()
                    sentence_buffer = ""

                    if sentence:
                        try:
                            audio_bytes = await asyncio.to_thread(
                                generate_tts_audio, sentence
                            )
                            audio_base64 = base64.b64encode(audio_bytes).decode()
                            await websocket.send_json({
                                "type": "audio_chunk",
                                "audio": audio_base64,
                                "text": sentence,
                            })
                        except Exception as e:
                            await websocket.send_json({
                                "type": "tts_error",
                                "message": str(e),
                            })

            # Handle remaining text
            if sentence_buffer.strip():
                try:
                    audio_bytes = await asyncio.to_thread(
                        generate_tts_audio, sentence_buffer.strip()
                    )
                    audio_base64 = base64.b64encode(audio_bytes).decode()
                    await websocket.send_json({
                        "type": "audio_chunk",
                        "audio": audio_base64,
                        "text": sentence_buffer.strip(),
                    })
                except Exception:
                    pass

            await websocket.send_json({
                "type": "llm_done",
                "full_response": full_response,
            })

        except httpx.ConnectError:
            try:
                await websocket.send_json({"type": "error", "message": "Cannot connect to Ollama"})
            except RuntimeError:
                return  # Client disconnected (barge-in)
        except WebSocketDisconnect:
            return
        except Exception as e:
            try:
                await websocket.send_json({"type": "error", "message": str(e)})
            except RuntimeError:
                return

        # Reset for next recording
        audio_buffer.reset()
        try:
            await websocket.send_json({"type": "vad_state", "state": "listening"})
        except RuntimeError:
            pass

    try:
        await websocket.send_json({"type": "vad_state", "state": "listening"})

        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "audio_chunk":
                # Decode base64 PCM audio
                audio_base64 = data.get("audio", "")
                if audio_base64:
                    pcm_data = base64.b64decode(audio_base64)
                    was_speech_detected = audio_buffer.speech_detected
                    vad_result = audio_buffer.add_chunk(pcm_data)

                    # Send speech state on first speech detection
                    if vad_result == "speech" and not was_speech_detected:
                        await websocket.send_json({"type": "vad_state", "state": "speech"})

                    if vad_result == "speech_ended":
                        await process_speech()

            elif msg_type == "stop":
                # Force end recording
                if audio_buffer.speech_detected:
                    await process_speech()

    except WebSocketDisconnect:
        pass
    finally:
        keepalive_task.cancel()


def run_server():
    """Entry point for uv run serve."""
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    run_server()
