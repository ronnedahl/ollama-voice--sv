"""LLM chat endpoint (non-streaming)."""

import httpx
from fastapi import APIRouter, HTTPException

from config import get_system_prompt
from schemas import ChatRequest, ChatResponse
from services import ollama
from state import conversation_memory, language_state

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
            "content": get_system_prompt(language_state.get()),
        })

    messages.extend(conversation_memory.as_messages())
    messages.append({"role": "user", "content": request.text})

    try:
        ai_response = await ollama.chat(messages)
        if not ai_response:
            raise HTTPException(status_code=500, detail="Empty response from Ollama")
        conversation_memory.add_turn(request.text, ai_response)
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
