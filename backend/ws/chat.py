"""WebSocket endpoint for streaming LLM + TTS responses."""

import asyncio
import base64
import re

import httpx
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from config import SYSTEM_PROMPT
from services import ollama
from services.tts import generate_tts_audio

router = APIRouter()


@router.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """Stream LLM tokens and sentence-level TTS audio over a WebSocket."""
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

                        await websocket.send_json({
                            "type": "llm_token",
                            "token": token,
                        })

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
