# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Local voice AI assistant (Swedish: "Lokal Röst-AI Assistent") - a fully local voice assistant system where users can speak to an AI and receive spoken responses. Runs entirely locally using open-source tools on NVIDIA GPU (12GB VRAM GTX 3060).

**Status**: Backend and frontend implemented.

## Architecture

**5-stage voice pipeline**: User Recording → Speech-to-Text → LLM Processing → Text-to-Speech → Audio Playback

**Target latency**: <5 seconds for full pipeline

### Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | Next.js 14+ (App Router), TypeScript, Web Audio API, MediaRecorder API |
| Backend | Python FastAPI |
| Speech-to-Text | faster-whisper or whisper.cpp (GPU/CUDA, Swedish language) |
| LLM | Ollama with Llama 3.1:8b or Mistral |
| Text-to-Speech | Piper TTS with sv_SE-nst-medium Swedish voice |

### Project Structure

```
voice-ai-local/
├── backend/
│   ├── main.py              # FastAPI server with all endpoints
│   └── pyproject.toml       # uv dependencies
├── frontend/
│   ├── app/
│   │   ├── layout.tsx       # Root layout
│   │   ├── page.tsx         # Main voice interface
│   │   └── globals.css
│   ├── components/
│   │   ├── VoiceRecorder.tsx
│   │   └── AudioPlayer.tsx
│   ├── lib/
│   │   └── api.ts           # Backend API client
│   └── package.json
└── CLAUDE.md
```

### API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/transcribe` | POST | Audio file → transcribed Swedish text (Whisper) |
| `/api/chat` | POST | Text query → AI response (Ollama) |
| `/api/tts` | POST | Text → audio bytes/base64 (Piper TTS) |

## Development Commands

```bash
# Backend (using uv)
cd backend
uv sync                          # Install dependencies
uv run uvicorn main:app --reload # Development server on port 8000

# Frontend
cd frontend
npm install
npm run dev  # runs on port 3000

# Model setup (run once)
ollama pull llama3.1:8b
```

## GPU Memory Budget

- Whisper medium: ~5GB VRAM
- Llama 3.1:8b: ~5GB VRAM
- Piper TTS: minimal
- **Total**: ~10-11GB (fits 12GB VRAM)

Verify GPU usage with `nvidia-smi`

## Key Implementation Notes

- CORS must be configured between localhost:3000 (Next.js) and localhost:8000 (FastAPI)
- Use float16 precision for Whisper on GPU
- Cache TTS model in memory for performance
- Consider Q4_K_M quantization for faster LLM inference
- Audio file size validation: max 10MB
- Privacy-first: no permanent data storage
