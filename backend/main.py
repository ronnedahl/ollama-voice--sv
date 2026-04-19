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
import json
import re
import subprocess
import tempfile
from pathlib import Path

import httpx
from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from config import (
    LANGUAGE,
    MAX_AUDIO_SIZE_MB,
    MUSIC_DIR,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    PIPER_MODEL,
    SYSTEM_PROMPT,
    WHISPER_MODEL,
)
from music import MusicLibrary, detect_play_command, detect_stop_command
from schemas import ChatRequest, ChatResponse, TranscribeResponse, TTSRequest
from services.tts import generate_tts_audio
from services.vad import AudioBuffer
from services.whisper import get_whisper_model, transcribe_audio_bytes

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

# Initialize music library
music_library = MusicLibrary(MUSIC_DIR)


@app.on_event("startup")
async def startup_event():
    music_library.scan()


def split_into_sentences(text: str) -> list[str]:
    """Split text into sentences for TTS streaming."""
    # Split on sentence endings, keeping the delimiter
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sentences if s.strip()]


@app.get("/")
async def root():
    return {
        "status": "ok",
        "service": "Local Voice AI Assistant",
        "endpoints": ["/api/transcribe", "/api/chat", "/api/tts"],
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "whisper_model": WHISPER_MODEL,
        "ollama_model": OLLAMA_MODEL,
        "tts_model": PIPER_MODEL,
    }


@app.get("/api/music/list")
async def list_music():
    """List all indexed music tracks."""
    return {"tracks": [t.to_dict() for t in music_library.tracks]}


@app.get("/api/music/file/{track_id}")
async def get_music_file(track_id: str):
    """Stream a music file by track ID."""
    track = music_library.get(track_id)
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
    return FileResponse(track.path, filename=track.filename)


@app.post("/api/music/rescan")
async def rescan_music():
    """Re-scan the music directory."""
    count = music_library.scan()
    return {"count": count}


@app.post("/api/transcribe", response_model=TranscribeResponse)
async def transcribe(audio: UploadFile = File(...)):
    """Transcribe audio to Swedish text using faster-whisper."""
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


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Generate AI response using Ollama LLM."""
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    messages = []
    if request.system_prompt:
        messages.append({"role": "system", "content": request.system_prompt})
    else:
        messages.append({
            "role": "system",
            "content": SYSTEM_PROMPT,
        })

    messages.append({"role": "user", "content": request.text})

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": OLLAMA_MODEL,
                    "messages": messages,
                    "stream": False,
                },
            )
            response.raise_for_status()
            data = response.json()

            ai_response = data.get("message", {}).get("content", "")
            if not ai_response:
                raise HTTPException(status_code=500, detail="Empty response from Ollama")

            return ChatResponse(response=ai_response)

    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail="Cannot connect to Ollama. Run: ollama serve",
        )
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Ollama request timed out")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"Ollama error: {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat failed: {e}")


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
                    async with httpx.AsyncClient(timeout=60.0) as client:
                        async with client.stream(
                            "POST",
                            f"{OLLAMA_BASE_URL}/api/chat",
                            json={
                                "model": OLLAMA_MODEL,
                                "messages": messages,
                                "stream": True,
                            },
                        ) as response:
                            full_response = ""
                            sentence_buffer = ""

                            async for line in response.aiter_lines():
                                if line:
                                    chunk = json.loads(line)
                                    if "message" in chunk:
                                        token = chunk["message"].get("content", "")
                                        if token:
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
                                                    # Generate TTS in background
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
            async with httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream(
                    "POST",
                    f"{OLLAMA_BASE_URL}/api/chat",
                    json={
                        "model": OLLAMA_MODEL,
                        "messages": messages,
                        "stream": True,
                    },
                ) as response:
                    full_response = ""
                    sentence_buffer = ""

                    async for line in response.aiter_lines():
                        if line:
                            chunk = json.loads(line)
                            if "message" in chunk:
                                token = chunk["message"].get("content", "")
                                if token:
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


@app.post("/api/tts")
async def text_to_speech(request: TTSRequest):
    """Convert text to speech using Piper TTS CLI."""
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    # Create temp file for output
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        output_path = tmp.name

    try:
        # Call piper via CLI: echo "text" | piper --model sv_SE-nst-medium --output_file out.wav
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
            background=None,  # Don't delete until response is sent
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


def run_server():
    """Entry point for uv run serve."""
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    run_server()
