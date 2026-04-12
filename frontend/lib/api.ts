const API_BASE = "http://localhost:8000";
const WS_BASE = "ws://localhost:8000";

export interface TranscribeResponse {
  text: string;
  language: string;
  confidence: number;
}

export interface ChatResponse {
  response: string;
}

export interface StreamCallbacks {
  onToken: (token: string) => void;
  onAudioChunk: (audioBase64: string, text: string) => void;
  onDone: (fullResponse: string) => void;
  onError: (error: string) => void;
}

export type VadState = "listening" | "speech" | "processing";

export interface Track {
  id: string;
  filename: string;
  title: string;
  artist: string;
}

export const API_BASE_URL = API_BASE;

export interface VoiceStreamCallbacks {
  onVadState: (state: VadState) => void;
  onTranscript: (text: string, confidence: number) => void;
  onToken: (token: string) => void;
  onAudioChunk: (audioBase64: string, text: string) => void;
  onDone: (fullResponse: string) => void;
  onError: (error: string) => void;
  onPlaySong?: (track: Track, url: string) => void;
  onStopMusic?: () => void;
  onMusicNotFound?: (query: string) => void;
}

export function createVoiceStream(callbacks: VoiceStreamCallbacks): WebSocket {
  const ws = new WebSocket(`${WS_BASE}/ws/voice`);

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);

    switch (data.type) {
      case "vad_state":
        callbacks.onVadState(data.state);
        break;
      case "transcript":
        callbacks.onTranscript(data.text, data.confidence);
        break;
      case "llm_token":
        callbacks.onToken(data.token);
        break;
      case "audio_chunk":
        callbacks.onAudioChunk(data.audio, data.text);
        break;
      case "llm_done":
        callbacks.onDone(data.full_response);
        break;
      case "play_song":
        callbacks.onPlaySong?.(data.track, data.url);
        break;
      case "stop_music":
        callbacks.onStopMusic?.();
        break;
      case "music_not_found":
        callbacks.onMusicNotFound?.(data.query);
        break;
      case "error":
      case "tts_error":
        callbacks.onError(data.message);
        break;
    }
  };

  ws.onerror = () => {
    callbacks.onError("WebSocket connection failed");
  };

  return ws;
}

export function sendAudioChunk(ws: WebSocket, pcmData: ArrayBuffer) {
  if (ws.readyState === WebSocket.OPEN) {
    const base64 = btoa(String.fromCharCode(...new Uint8Array(pcmData)));
    ws.send(JSON.stringify({ type: "audio_chunk", audio: base64 }));
  }
}

export function stopRecording(ws: WebSocket) {
  if (ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: "stop" }));
  }
}

export function streamChat(text: string, callbacks: StreamCallbacks): WebSocket {
  const ws = new WebSocket(`${WS_BASE}/ws/chat`);

  ws.onopen = () => {
    ws.send(JSON.stringify({ type: "chat", text, tts: true }));
  };

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);

    switch (data.type) {
      case "llm_token":
        callbacks.onToken(data.token);
        break;
      case "audio_chunk":
        callbacks.onAudioChunk(data.audio, data.text);
        break;
      case "llm_done":
        callbacks.onDone(data.full_response);
        ws.close();
        break;
      case "error":
      case "tts_error":
        callbacks.onError(data.message);
        break;
    }
  };

  ws.onerror = () => {
    callbacks.onError("WebSocket connection failed");
  };

  return ws;
}

export async function transcribeAudio(audioBlob: Blob): Promise<TranscribeResponse> {
  const formData = new FormData();
  formData.append("audio", audioBlob, "recording.webm");

  const response = await fetch(`${API_BASE}/api/transcribe`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Transcription failed" }));
    throw new Error(error.detail || "Transcription failed");
  }

  return response.json();
}

export async function chat(text: string): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Chat failed" }));
    throw new Error(error.detail || "Chat failed");
  }

  return response.json();
}

export async function textToSpeech(text: string): Promise<Blob> {
  const response = await fetch(`${API_BASE}/api/tts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "TTS failed" }));
    throw new Error(error.detail || "TTS failed");
  }

  return response.blob();
}
