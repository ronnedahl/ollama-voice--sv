"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { createVoiceStream, sendAudioChunk, stopRecording, VadState } from "@/lib/api";

export type Status = "idle" | "listening" | "speech" | "processing" | "streaming" | "speaking" | "error";

function base64ToBlob(base64: string): Blob {
  const byteCharacters = atob(base64);
  const byteNumbers = new Array(byteCharacters.length);
  for (let i = 0; i < byteCharacters.length; i++) {
    byteNumbers[i] = byteCharacters.charCodeAt(i);
  }
  return new Blob([new Uint8Array(byteNumbers)], { type: "audio/wav" });
}

export function useVoicePipeline() {
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);
  const [analyser, setAnalyser] = useState<AnalyserNode | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const audioQueueRef = useRef<Blob[]>([]);
  const isPlayingRef = useRef(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const llmDoneRef = useRef(false);
  const playbackCtxRef = useRef<AudioContext | null>(null);
  const playbackAnalyserRef = useRef<AnalyserNode | null>(null);

  const playNextAudio = useCallback(() => {
    if (audioQueueRef.current.length === 0) {
      isPlayingRef.current = false;
      if (llmDoneRef.current) {
        setStatus("idle");
        setAnalyser(null);
      }
      return;
    }
    isPlayingRef.current = true;
    setStatus("speaking");
    if (playbackAnalyserRef.current) setAnalyser(playbackAnalyserRef.current);

    const url = URL.createObjectURL(audioQueueRef.current.shift()!);
    if (audioRef.current) {
      audioRef.current.src = url;
      audioRef.current.play().catch(console.error);
    }
  }, []);

  useEffect(() => {
    const audio = new Audio();
    audio.crossOrigin = "anonymous";
    audio.onended = playNextAudio;
    audio.onerror = playNextAudio;
    audioRef.current = audio;

    // Set up playback analyser
    try {
      const ctx = new AudioContext();
      const source = ctx.createMediaElementSource(audio);
      const an = ctx.createAnalyser();
      an.fftSize = 128;
      source.connect(an);
      an.connect(ctx.destination);
      playbackCtxRef.current = ctx;
      playbackAnalyserRef.current = an;
    } catch (e) {
      console.error("Playback analyser setup failed:", e);
    }

    return () => {
      audio.pause();
      audio.src = "";
      playbackCtxRef.current?.close();
    };
  }, [playNextAudio]);

  const stopMicrophone = useCallback(() => {
    processorRef.current?.disconnect();
    processorRef.current = null;
    audioContextRef.current?.close();
    audioContextRef.current = null;
    streamRef.current?.getTracks().forEach(t => t.stop());
    streamRef.current = null;
  }, []);

  const startListening = useCallback(async () => {
    setError(null);
    audioQueueRef.current = [];
    llmDoneRef.current = false;

    const ws = createVoiceStream({
      onVadState: (state: VadState) => {
        if (state === "listening") setStatus("listening");
        else if (state === "speech") setStatus("speech");
        else if (state === "processing") {
          setStatus("processing");
          stopMicrophone();
          setAnalyser(null);
        }
      },
      onTranscript: () => setStatus("streaming"),
      onToken: () => {},
      onAudioChunk: (audioBase64) => {
        audioQueueRef.current.push(base64ToBlob(audioBase64));
        if (!isPlayingRef.current) playNextAudio();
      },
      onDone: () => {
        llmDoneRef.current = true;
        if (!isPlayingRef.current && audioQueueRef.current.length === 0) {
          setStatus("idle");
          setAnalyser(null);
        }
      },
      onError: (msg) => {
        setError(msg);
        setStatus("error");
        stopMicrophone();
        setAnalyser(null);
      },
    });

    wsRef.current = ws;
    await new Promise<void>((resolve, reject) => {
      ws.onopen = () => resolve();
      ws.onerror = () => reject(new Error("WebSocket failed"));
    });

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true },
      });
      streamRef.current = stream;

      const ctx = new AudioContext();
      audioContextRef.current = ctx;
      const inputRate = ctx.sampleRate;
      const targetRate = 16000;

      const source = ctx.createMediaStreamSource(stream);

      // Set up mic analyser for visualization
      const micAnalyser = ctx.createAnalyser();
      micAnalyser.fftSize = 128;
      source.connect(micAnalyser);
      setAnalyser(micAnalyser);

      const processor = ctx.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;

      processor.onaudioprocess = (e) => {
        if (ws.readyState !== WebSocket.OPEN) return;
        const input = e.inputBuffer.getChannelData(0);

        let resampled: Float32Array;
        if (inputRate !== targetRate) {
          const ratio = inputRate / targetRate;
          const len = Math.round(input.length / ratio);
          resampled = new Float32Array(len);
          for (let i = 0; i < len; i++) resampled[i] = input[Math.floor(i * ratio)];
        } else {
          resampled = input;
        }

        const int16 = new Int16Array(resampled.length);
        for (let i = 0; i < resampled.length; i++) {
          const s = Math.max(-1, Math.min(1, resampled[i]));
          int16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
        }
        sendAudioChunk(ws, int16.buffer);
      };

      source.connect(processor);
      processor.connect(ctx.destination);
      setStatus("listening");
    } catch {
      setError("Kunde inte komma åt mikrofonen.");
      setStatus("error");
      ws.close();
    }
  }, [stopMicrophone, playNextAudio]);

  const handleStop = useCallback(() => {
    if (wsRef.current) stopRecording(wsRef.current);
  }, []);

  const isActive = status !== "idle" && status !== "error";
  const isRecording = status === "listening" || status === "speech";

  return {
    status, error, analyser,
    isActive, isRecording,
    startListening, handleStop,
  };
}
