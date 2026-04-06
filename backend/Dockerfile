FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# System dependencies for piper-tts and audio processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-dev \
    python3-venv \
    python3-pip \
    gcc \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Install dependencies
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev

# Download Piper TTS Swedish voice model
RUN mkdir -p /app/voices && \
    curl -L -o /app/voices/sv_SE-nst-medium.onnx \
    "https://huggingface.co/rhasspy/piper-voices/resolve/main/sv/sv_SE/nst/medium/sv_SE-nst-medium.onnx" && \
    curl -L -o /app/voices/sv_SE-nst-medium.onnx.json \
    "https://huggingface.co/rhasspy/piper-voices/resolve/main/sv/sv_SE/nst/medium/sv_SE-nst-medium.onnx.json"

# Copy application code
COPY main.py .

ENV PIPER_MODEL=/app/voices/sv_SE-nst-medium.onnx
ENV OLLAMA_BASE_URL=http://ollama:11434

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
