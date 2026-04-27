"""Language settings endpoints (GET current language, POST to change)."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.language import UnsupportedLanguageError
from state import conversation_memory, language_state

router = APIRouter(prefix="/api", tags=["language"])


class LanguageResponse(BaseModel):
    language: str


class LanguageRequest(BaseModel):
    language: str


@router.get("/language", response_model=LanguageResponse)
async def get_language():
    return LanguageResponse(language=language_state.get())


@router.post("/language", response_model=LanguageResponse)
async def set_language(request: LanguageRequest):
    """Switch the active language and clear conversation memory.

    Memory is cleared for the same reason as the voice-command path: prior-
    language turns drag the LLM back into the wrong language.
    """
    try:
        language_state.set(request.language)
    except UnsupportedLanguageError as e:
        raise HTTPException(status_code=400, detail=str(e))
    conversation_memory.clear()
    return LanguageResponse(language=language_state.get())
