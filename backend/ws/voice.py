"""Unified WebSocket endpoint for the full voice pipeline with VAD."""

import asyncio
import base64
import re

import httpx
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from config import get_system_prompt
from music import detect_play_command, detect_stop_command
from services import ollama
from services.tts import generate_tts_audio
from services.vad import AudioBuffer
from services.whisper import transcribe_audio_bytes
from state import conversation_memory, language_state, music_library

router = APIRouter()


@router.websocket("/ws/voice")
async def websocket_voice(websocket: WebSocket):
    """Full voice pipeline: audio chunks → VAD → STT → LLM → TTS.

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

        wav_bytes = audio_buffer.get_wav_bytes()

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

        # LLM + TTS streaming (with last 6 turn-pair memory)
        messages = [
            {"role": "system", "content": get_system_prompt(language_state.get())},
            *conversation_memory.as_messages(),
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

            conversation_memory.add_turn(text, full_response)

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
                audio_base64 = data.get("audio", "")
                if audio_base64:
                    pcm_data = base64.b64decode(audio_base64)
                    was_speech_detected = audio_buffer.speech_detected
                    vad_result = audio_buffer.add_chunk(pcm_data)

                    if vad_result == "speech" and not was_speech_detected:
                        await websocket.send_json({"type": "vad_state", "state": "speech"})

                    if vad_result == "speech_ended":
                        await process_speech()

            elif msg_type == "stop":
                if audio_buffer.speech_detected:
                    await process_speech()

    except WebSocketDisconnect:
        pass
    finally:
        keepalive_task.cancel()
