# Local Voice AI Assistant

A fully local voice assistant where you talk to an AI and get spoken responses. Runs 100% locally using open-source tools on NVIDIA GPU. Designed for Swedish language.

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Next.js](https://img.shields.io/badge/Next.js-14-black)
![License](https://img.shields.io/badge/License-MIT-green)

## Overview

**5-stage voice pipeline:** Recording → Speech-to-Text → LLM → Text-to-Speech → Playback

- **Speech-to-Text**: faster-whisper (Swedish, GPU/CUDA)
- **LLM**: Ollama with Llama 3.1:8b
- **Text-to-Speech**: Piper TTS with Swedish voice (sv_SE-nst-medium)
- **Frontend**: Next.js 14 with Web Audio API
- **Backend**: Python FastAPI with WebSocket support

Target latency: <5 seconds for the full pipeline.

## Prerequisites

- NVIDIA GPU with at least 12 GB VRAM (e.g. RTX 3060)
- [Ollama](https://ollama.ai) installed
- Python 3.10+
- Node.js 18+
- [uv](https://docs.astral.sh/uv/) (Python package manager)

## Installation

### 1. Clone the repo

```bash
git clone <repo-url>
cd ollama-voice-sv
```

### 2. Download the LLM model

```bash
ollama pull llama3.1:8b
```

### 3. Backend

```bash
cd backend
uv sync
```

### 4. Frontend

```bash
cd frontend
npm install
```

## Usage

Run in two separate terminals:

```bash
# Terminal 1 - Backend (port 8000)
cd backend
uv run uvicorn main:app --reload

# Terminal 2 - Frontend (port 3000)
cd frontend
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/transcribe` | POST | Audio file → transcribed text (Whisper) |
| `/api/chat` | POST | Text → AI response (Ollama) |
| `/api/tts` | POST | Text → audio data (Piper TTS) |
| `/ws/chat` | WebSocket | Streaming LLM + TTS |
| `/ws/voice` | WebSocket | Full voice pipeline with VAD |

## GPU Memory Budget

| Component | VRAM |
|-----------|------|
| Whisper medium | ~5 GB |
| Llama 3.1:8b | ~5 GB |
| Piper TTS | minimal |
| **Total** | **~10-11 GB** |

Verify with `nvidia-smi`.

## Project Structure

```
ollama-voice-sv/
├── backend/
│   ├── main.py              # FastAPI server with all endpoints
│   └── pyproject.toml       # Python dependencies (uv)
├── frontend/
│   ├── app/                 # Next.js App Router
│   ├── components/          # React components
│   ├── lib/api.ts           # API client
│   └── package.json
├── CLAUDE.md
└── README.md
```

## Privacy

All data is processed locally. Nothing is sent to external services or stored permanently.
