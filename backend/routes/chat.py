"""LLM chat endpoint (non-streaming)."""

import httpx
from fastapi import APIRouter, HTTPException

from config import SYSTEM_PROMPT
from schemas import ChatRequest, ChatResponse
from services import ollama

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
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
        ai_response = await ollama.chat(messages)
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
