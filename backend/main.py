"""Local Voice AI Assistant — FastAPI application bootstrap."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes import chat as chat_route
from routes import health as health_route
from routes import language as language_route
from routes import music as music_route
from routes import transcribe as transcribe_route
from routes import tts as tts_route
from state import music_library
from ws import chat as chat_ws
from ws import voice as voice_ws

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
app.include_router(language_route.router)
app.include_router(music_route.router)
app.include_router(transcribe_route.router)
app.include_router(chat_route.router)
app.include_router(tts_route.router)
app.include_router(chat_ws.router)
app.include_router(voice_ws.router)


@app.on_event("startup")
async def startup_event():
    music_library.scan()


def run_server():
    """Entry point for uv run serve."""
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    run_server()
