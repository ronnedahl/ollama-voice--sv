"use client";

import { useState, useRef, useCallback } from "react";

interface VoiceRecorderProps {
  onRecordingComplete: (blob: Blob) => void;
  disabled?: boolean;
}

export default function VoiceRecorder({ onRecordingComplete, disabled }: VoiceRecorderProps) {
  const [isRecording, setIsRecording] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const startRecording = useCallback(async () => {
    try {
      setError(null);
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: "audio/webm;codecs=opus",
      });

      mediaRecorderRef.current = mediaRecorder;
      chunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        onRecordingComplete(blob);
        stream.getTracks().forEach((track) => track.stop());
      };

      mediaRecorder.start();
      setIsRecording(true);
    } catch (err) {
      setError("Kunde inte komma åt mikrofonen. Kontrollera behörigheter.");
      console.error("Microphone access error:", err);
    }
  }, [onRecordingComplete]);

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  }, [isRecording]);

  return (
    <div className="voice-recorder">
      <button
        onClick={isRecording ? stopRecording : startRecording}
        disabled={disabled}
        className={`record-button ${isRecording ? "recording" : ""}`}
      >
        {isRecording ? "⏹ Sluta prata" : "🎤 Börja prata"}
      </button>

      {isRecording && (
        <div className="recording-indicator">
          <span className="pulse"></span>
          Spelar in...
        </div>
      )}

      {error && <div className="error">{error}</div>}

      <style jsx>{`
        .voice-recorder {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 1rem;
        }

        .record-button {
          padding: 1rem 2rem;
          font-size: 1.25rem;
          border: none;
          border-radius: 50px;
          cursor: pointer;
          transition: all 0.2s;
          background: #2563eb;
          color: white;
        }

        .record-button:hover:not(:disabled) {
          background: #1d4ed8;
          transform: scale(1.05);
        }

        .record-button:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .record-button.recording {
          background: #dc2626;
          animation: pulse-bg 1.5s infinite;
        }

        @keyframes pulse-bg {
          0%, 100% { background: #dc2626; }
          50% { background: #ef4444; }
        }

        .recording-indicator {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          color: #dc2626;
          font-weight: 500;
        }

        .pulse {
          width: 12px;
          height: 12px;
          background: #dc2626;
          border-radius: 50%;
          animation: pulse 1s infinite;
        }

        @keyframes pulse {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.5; transform: scale(1.2); }
        }

        .error {
          color: #dc2626;
          background: #fef2f2;
          padding: 0.75rem 1rem;
          border-radius: 8px;
          font-size: 0.9rem;
        }
      `}</style>
    </div>
  );
}
