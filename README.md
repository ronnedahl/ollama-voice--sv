# Local Voice AI Assistant

A fully local voice assistant where you talk to an AI and get spoken responses — no cloud APIs, no data leaving your machine. Runs on an NVIDIA GPU and supports Swedish and English voices.

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Next.js](https://img.shields.io/badge/Next.js-14-black)
![Docker](https://img.shields.io/badge/Docker-ready-2496ED)
![License](https://img.shields.io/badge/License-MIT-green)

## Overview

**5-stage voice pipeline:** Recording → Speech-to-Text → LLM → Text-to-Speech → Playback

- **Speech-to-Text**: faster-whisper (GPU/CUDA)
- **LLM**: Ollama with Llama 3.1:8b
- **Text-to-Speech**: Piper TTS (Swedish `sv_SE-nst-medium` or English `en_US-amy-medium`)
- **Frontend**: Next.js 14 with Web Audio API, MediaRecorder, WebSocket streaming
- **Backend**: Python FastAPI with REST + WebSocket endpoints, WebRTC VAD

Target latency: <5 seconds for the full pipeline.

## Features

- Real-time streaming voice pipeline over WebSocket
- Voice Activity Detection (WebRTC VAD) with automatic silence-based cutoff
- Streaming LLM token output with incremental TTS
- Local music playback by voice command (`play song-one`, `stop the music`, or Swedish `spela låten …`, `stoppa musiken`)
- Markdown stripping before TTS so the model doesn't read `**bold**` as "asterisk asterisk"
- Swedish and English voices (switched via `LANGUAGE` env var)

## Prerequisites

- NVIDIA GPU with ≥12 GB VRAM (e.g. RTX 3060)
- [Docker](https://docs.docker.com/get-docker/) with [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)
- [Ollama](https://ollama.ai) running on the host (`ollama serve`)

For manual (non-Docker) runs you also need Python 3.10+, Node.js 18+, and [uv](https://docs.astral.sh/uv/).

## Quick Start (Docker)

### 1. Pull the LLM model

```bash
ollama pull llama3.1:8b
```

Make sure `ollama serve` is running on the host — the backend container reaches it via `localhost:11434` (host network).

### 2. Start everything

From the project root:

```bash
docker compose up -d --build
```

This starts:
- `voice-backend` on port **8000** (host network, GPU-enabled)
- `voice-frontend` on port **3001**

Open [http://localhost:3001](http://localhost:3001).

### 3. Useful commands

```bash
docker compose ps                  # status
docker compose logs -f backend     # follow backend logs
docker compose down                # stop everything
```

### Configuration

Environment variables (see `docker-compose.yml`):

| Var | Default | Purpose |
|-----|---------|---------|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama host URL |
| `OLLAMA_MODEL` | `llama3.1:8b` | LLM model name |
| `PIPER_MODEL` | `/app/voices/en_US-amy-medium.onnx` | TTS voice model |
| `LANGUAGE` | `en` | `en` or `sv` — sets system prompt + expected voice language |
| `WHISPER_MODEL` | `small` | Whisper size (`tiny`/`base`/`small`/`medium`) |
| `MUSIC_DIR` | `/music` | Mounted music folder (change the volume in compose) |

The music folder is mounted read-only; adjust the `volumes:` line in `docker-compose.yml` to point at your own music directory.

## Manual Setup (without Docker)

```bash
# Backend
cd backend
uv sync
uv run uvicorn main:app --reload   # port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev                        # port 3000
```

Then open [http://localhost:3000](http://localhost:3000).

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/transcribe` | POST | Audio file → transcribed text (Whisper) |
| `/api/chat` | POST | Text → AI response (Ollama) |
| `/api/tts` | POST | Text → audio data (Piper TTS) |
| `/api/music/*` | GET/POST | List and control local music playback |
| `/ws/chat` | WebSocket | Streaming LLM + TTS |
| `/ws/voice` | WebSocket | Full voice pipeline with VAD |

## GPU Memory Budget

| Component | VRAM |
|-----------|------|
| Whisper small/medium | ~2–5 GB |
| Llama 3.1:8b | ~5 GB |
| Piper TTS | minimal |
| **Total** | **~8–11 GB** |

Verify with `nvidia-smi`.

## Project Structure

```
ollama-voice-sv/
├── backend/
│   ├── main.py              # FastAPI bootstrap + router registration
│   ├── config.py            # Env vars and constants
│   ├── schemas.py           # Pydantic request/response models
│   ├── state.py             # Shared singletons (e.g. music library)
│   ├── music.py             # Music library + voice-command regex
│   ├── routes/              # REST endpoints (chat, tts, transcribe, music, health)
│   ├── services/            # whisper, ollama, tts, vad
│   ├── ws/                  # WebSocket handlers (chat, voice)
│   ├── voices/              # Piper voice models (.onnx)
│   ├── Dockerfile
│   └── pyproject.toml
├── frontend/
│   ├── app/                 # Next.js App Router
│   ├── components/          # VoiceRecorder, AudioPlayer, NowPlaying, Waveform, StatusLabel
│   ├── hooks/               # useVoicePipeline, useMusicPlayer
│   ├── lib/api.ts           # Backend API client
│   ├── Dockerfile
│   └── package.json
├── scripts/
│   └── ollama-init.sh
├── docker-compose.yml
├── CLAUDE.md
└── README.md
```

## Privacy

All audio, transcripts, and LLM responses are processed locally. Nothing is sent to external services or stored permanently.

## License

MIT
