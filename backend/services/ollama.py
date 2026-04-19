"""Ollama chat helpers (one-shot and streaming)."""

import json
from typing import AsyncIterator

import httpx

from config import OLLAMA_BASE_URL, OLLAMA_MODEL


async def chat(messages: list[dict]) -> str:
    """Return the full assistant reply for `messages` (non-streaming)."""
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
        return data.get("message", {}).get("content", "")


async def stream_chat(messages: list[dict]) -> AsyncIterator[str]:
    """Yield assistant tokens from Ollama as they arrive."""
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
            async for line in response.aiter_lines():
                if not line:
                    continue
                chunk = json.loads(line)
                if "message" not in chunk:
                    continue
                token = chunk["message"].get("content", "")
                if token:
                    yield token
