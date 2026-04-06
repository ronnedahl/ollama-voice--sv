"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { createVoiceStream, sendAudioChunk, stopRecording, VadState } from "@/lib/api";

type Status = "idle" | "listening" | "speech" | "processing" | "streaming" | "speaking" | "error";

interface Message {
  role: "user" | "assistant";
  text: string;
}

function base64ToBlob(base64: string, mimeType: string = "audio/wav"): Blob {
  const byteCharacters = atob(base64);
  const byteNumbers = new Array(byteCharacters.length);
  for (let i = 0; i < byteCharacters.length; i++) {
    byteNumbers[i] = byteCharacters.charCodeAt(i);
  }
  const byteArray = new Uint8Array(byteNumbers);
  return new Blob([byteArray], { type: mimeType });
}

export default function Home() {
  const [status, setStatus] = useState<Status>("idle");
  const [messages, setMessages] = useState<Message[]>([]);
  const [streamingText, setStreamingText] = useState<string>("");
  const [transcriptText, setTranscriptText] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  // Audio playback queue
  const audioQueueRef = useRef<Blob[]>([]);
  const isPlayingRef = useRef<boolean>(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const llmDoneRef = useRef<boolean>(false);

  const playNextAudio = useCallback(() => {
    if (audioQueueRef.current.length === 0) {
      isPlayingRef.current = false;
      if (llmDoneRef.current) {
        setStatus("idle");
      }
      return;
    }

    isPlayingRef.current = true;
    setStatus("speaking");

    const audioBlob = audioQueueRef.current.shift()!;
    const url = URL.createObjectURL(audioBlob);

    if (audioRef.current) {
      audioRef.current.src = url;
      audioRef.current.play().catch(console.error);
    }
  }, []);

  const queueAudio = useCallback((audioBlob: Blob) => {
    audioQueueRef.current.push(audioBlob);
    if (!isPlayingRef.current) {
      playNextAudio();
    }
  }, [playNextAudio]);

  // Initialize audio element
  useEffect(() => {
    const audio = new Audio();
    audio.onended = playNextAudio;
    audio.onerror = playNextAudio;
    audioRef.current = audio;

    return () => {
      audio.pause();
      audio.src = "";
    };
  }, [playNextAudio]);

  const stopMicrophone = useCallback(() => {
    if (processorRef.current) {
      processorRef.current.disconnect();
      processorRef.current = null;
    }
    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }
  }, []);

  const startListening = useCallback(async () => {
    setError(null);
    setStreamingText("");
    setTranscriptText("");
    audioQueueRef.current = [];
    llmDoneRef.current = false;

    // Create WebSocket connection
    const ws = createVoiceStream({
      onVadState: (state: VadState) => {
        if (state === "listening") {
          setStatus("listening");
        } else if (state === "speech") {
          setStatus("speech");
        } else if (state === "processing") {
          setStatus("processing");
          stopMicrophone();
        }
      },
      onTranscript: (text, _confidence) => {
        setTranscriptText(text);
        setMessages((prev) => [...prev, { role: "user", text }]);
        setStatus("streaming");
      },
      onToken: (token) => {
        setStreamingText((prev) => prev + token);
      },
      onAudioChunk: (audioBase64, _text) => {
        const audioBlob = base64ToBlob(audioBase64);
        queueAudio(audioBlob);
      },
      onDone: (fullResponse) => {
        setMessages((prev) => [...prev, { role: "assistant", text: fullResponse }]);
        setStreamingText("");
        llmDoneRef.current = true;
        if (!isPlayingRef.current && audioQueueRef.current.length === 0) {
          setStatus("idle");
        }
      },
      onError: (errorMsg) => {
        setError(errorMsg);
        setStatus("error");
        stopMicrophone();
      },
    });

    wsRef.current = ws;

    // Wait for WebSocket to open
    await new Promise<void>((resolve, reject) => {
      ws.onopen = () => resolve();
      ws.onerror = () => reject(new Error("WebSocket failed to connect"));
    });

    // Start microphone and stream audio
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
        }
      });
      streamRef.current = stream;

      const audioContext = new AudioContext();
      audioContextRef.current = audioContext;
      const inputSampleRate = audioContext.sampleRate;
      const targetSampleRate = 16000;

      const source = audioContext.createMediaStreamSource(stream);
      const processor = audioContext.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;

      processor.onaudioprocess = (e) => {
        if (ws.readyState === WebSocket.OPEN) {
          const inputData = e.inputBuffer.getChannelData(0);

          // Resample to 16kHz if needed
          let resampledData: Float32Array;
          if (inputSampleRate !== targetSampleRate) {
            const ratio = inputSampleRate / targetSampleRate;
            const newLength = Math.round(inputData.length / ratio);
            resampledData = new Float32Array(newLength);
            for (let i = 0; i < newLength; i++) {
              const srcIndex = Math.floor(i * ratio);
              resampledData[i] = inputData[srcIndex];
            }
          } else {
            resampledData = inputData;
          }

          // Convert float32 to int16
          const int16Data = new Int16Array(resampledData.length);
          for (let i = 0; i < resampledData.length; i++) {
            const s = Math.max(-1, Math.min(1, resampledData[i]));
            int16Data[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
          }
          sendAudioChunk(ws, int16Data.buffer);
        }
      };

      source.connect(processor);
      processor.connect(audioContext.destination);

      setStatus("listening");

    } catch (err) {
      console.error("Microphone error:", err);
      setError("Kunde inte komma åt mikrofonen. Kontrollera behörigheter.");
      setStatus("error");
      ws.close();
    }
  }, [queueAudio, stopMicrophone]);

  const handleStopClick = useCallback(() => {
    if (wsRef.current) {
      stopRecording(wsRef.current);
    }
  }, []);

  const statusText: Record<Status, string> = {
    idle: "Klicka för att prata",
    listening: "Lyssnar...",
    speech: "Pratar...",
    processing: "Bearbetar...",
    streaming: "AI svarar...",
    speaking: "Spelar upp...",
    error: "Ett fel uppstod",
  };

  const isActive = status !== "idle" && status !== "error";
  const isRecording = status === "listening" || status === "speech";

  return (
    <main className="container">
      <h1>Röst-AI Assistent</h1>
      <p className="subtitle">Prata med din lokala AI på svenska</p>

      <div className="status-badge" data-status={status}>
        {statusText[status]}
      </div>

      <button
        onClick={isRecording ? handleStopClick : startListening}
        disabled={isActive && !isRecording}
        className={`voice-button ${isRecording ? "recording" : ""} ${status === "speech" ? "speech-detected" : ""}`}
      >
        {isRecording ? "⏹ Stoppa" : "🎤 Börja prata"}
      </button>

      {error && <div className="error-message">{error}</div>}

      {transcriptText && status === "streaming" && (
        <div className="transcript">
          <span className="label">Du sa:</span>
          <p>{transcriptText}</p>
        </div>
      )}

      {streamingText && (
        <div className="streaming-response">
          <span className="streaming-label">AI svarar:</span>
          <p>{streamingText}<span className="cursor">|</span></p>
        </div>
      )}

      {messages.length > 0 && (
        <div className="messages">
          <h2>Konversation</h2>
          {messages.map((msg, idx) => (
            <div key={idx} className={`message ${msg.role}`}>
              <span className="role">{msg.role === "user" ? "Du" : "AI"}</span>
              <p>{msg.text}</p>
            </div>
          ))}
        </div>
      )}

      <style jsx>{`
        .container {
          min-height: 100vh;
          padding: 2rem;
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 1.5rem;
        }

        h1 {
          font-size: 2.5rem;
          font-weight: 700;
          color: white;
          margin-top: 2rem;
        }

        .subtitle {
          color: #a5b4fc;
          font-size: 1.1rem;
          margin-bottom: 1rem;
        }

        .status-badge {
          padding: 0.5rem 1rem;
          border-radius: 20px;
          font-size: 0.9rem;
          font-weight: 500;
          background: rgba(255, 255, 255, 0.1);
          color: #e2e8f0;
        }

        .status-badge[data-status="listening"] {
          background: #3b82f6;
          animation: pulse 1.5s infinite;
        }

        .status-badge[data-status="speech"] {
          background: #10b981;
          animation: pulse 0.5s infinite;
        }

        .status-badge[data-status="processing"],
        .status-badge[data-status="streaming"] {
          background: #8b5cf6;
          animation: pulse 1.5s infinite;
        }

        .status-badge[data-status="speaking"] {
          background: #10b981;
        }

        .status-badge[data-status="error"] {
          background: #ef4444;
        }

        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.7; }
        }

        .voice-button {
          padding: 1.5rem 3rem;
          font-size: 1.5rem;
          border: none;
          border-radius: 50px;
          cursor: pointer;
          transition: all 0.2s;
          background: #2563eb;
          color: white;
          font-weight: 600;
        }

        .voice-button:hover:not(:disabled) {
          background: #1d4ed8;
          transform: scale(1.05);
        }

        .voice-button:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .voice-button.recording {
          background: #dc2626;
          animation: pulse-bg 1.5s infinite;
        }

        .voice-button.speech-detected {
          background: #10b981;
          animation: pulse-bg 0.3s infinite;
        }

        @keyframes pulse-bg {
          0%, 100% { transform: scale(1); }
          50% { transform: scale(1.05); }
        }

        .error-message {
          background: #fef2f2;
          color: #dc2626;
          padding: 1rem 1.5rem;
          border-radius: 8px;
          max-width: 400px;
          text-align: center;
        }

        .transcript {
          width: 100%;
          max-width: 600px;
          background: rgba(16, 185, 129, 0.1);
          border: 1px solid rgba(16, 185, 129, 0.3);
          border-radius: 12px;
          padding: 1rem 1.5rem;
        }

        .transcript .label {
          font-size: 0.75rem;
          font-weight: 600;
          text-transform: uppercase;
          color: #10b981;
          display: block;
          margin-bottom: 0.5rem;
        }

        .transcript p {
          color: #e2e8f0;
          margin: 0;
        }

        .streaming-response {
          width: 100%;
          max-width: 600px;
          background: rgba(59, 130, 246, 0.1);
          border: 1px solid rgba(59, 130, 246, 0.3);
          border-radius: 12px;
          padding: 1rem 1.5rem;
        }

        .streaming-label {
          font-size: 0.75rem;
          font-weight: 600;
          text-transform: uppercase;
          color: #3b82f6;
          display: block;
          margin-bottom: 0.5rem;
        }

        .streaming-response p {
          color: #e2e8f0;
          line-height: 1.6;
          margin: 0;
        }

        .cursor {
          animation: blink 1s infinite;
          color: #3b82f6;
        }

        @keyframes blink {
          0%, 50% { opacity: 1; }
          51%, 100% { opacity: 0; }
        }

        .messages {
          width: 100%;
          max-width: 600px;
          margin-top: 2rem;
          background: rgba(255, 255, 255, 0.05);
          border-radius: 16px;
          padding: 1.5rem;
        }

        .messages h2 {
          font-size: 1.2rem;
          color: #a5b4fc;
          margin-bottom: 1rem;
          font-weight: 600;
        }

        .message {
          padding: 1rem;
          border-radius: 12px;
          margin-bottom: 0.75rem;
        }

        .message.user {
          background: rgba(59, 130, 246, 0.2);
          border-left: 3px solid #3b82f6;
        }

        .message.assistant {
          background: rgba(16, 185, 129, 0.2);
          border-left: 3px solid #10b981;
        }

        .role {
          font-size: 0.75rem;
          font-weight: 600;
          text-transform: uppercase;
          color: #94a3b8;
          display: block;
          margin-bottom: 0.25rem;
        }

        .message p {
          color: #e2e8f0;
          line-height: 1.5;
        }
      `}</style>
    </main>
  );
}
