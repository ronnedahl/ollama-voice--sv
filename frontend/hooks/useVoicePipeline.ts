"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { createVoiceStream, sendAudioChunk, stopRecording, VadState, Track, Language } from "@/lib/api";

interface UseVoicePipelineOptions {
  onPlaySong?: (track: Track, url: string) => void;
  onStopMusic?: () => void;
  onLanguageChanged?: (language: Language) => void;
}

export type Status = "idle" | "listening" | "speech" | "processing" | "streaming" | "speaking" | "error";

// Barge-in detection thresholds
const BARGE_IN_VOLUME_THRESHOLD = 20; // 0-255, higher = less sensitive
const BARGE_IN_FRAMES_REQUIRED = 4;   // ~65ms at 60fps

function base64ToBlob(base64: string): Blob {
  const byteCharacters = atob(base64);
  const byteNumbers = new Array(byteCharacters.length);
  for (let i = 0; i < byteCharacters.length; i++) {
    byteNumbers[i] = byteCharacters.charCodeAt(i);
  }
  return new Blob([new Uint8Array(byteNumbers)], { type: "audio/wav" });
}

export function useVoicePipeline(options: UseVoicePipelineOptions = {}) {
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);
  const [analyser, setAnalyser] = useState<AnalyserNode | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const micAnalyserRef = useRef<AnalyserNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const audioQueueRef = useRef<Blob[]>([]);
  const isPlayingRef = useRef(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const llmDoneRef = useRef(false);
  const playbackCtxRef = useRef<AudioContext | null>(null);
  const playbackAnalyserRef = useRef<AnalyserNode | null>(null);
  const bargeInRafRef = useRef<number | null>(null);
  const statusRef = useRef<Status>("idle");
  const isSendingAudioRef = useRef(false);

  useEffect(() => { statusRef.current = status; }, [status]);

  const stopSendingAudio = useCallback(() => {
    isSendingAudioRef.current = false;
  }, []);

  const releaseMicrophone = useCallback(() => {
    processorRef.current?.disconnect();
    processorRef.current = null;
    sourceRef.current?.disconnect();
    sourceRef.current = null;
    micAnalyserRef.current?.disconnect();
    micAnalyserRef.current = null;
    audioContextRef.current?.close();
    audioContextRef.current = null;
    streamRef.current?.getTracks().forEach(t => t.stop());
    streamRef.current = null;
  }, []);

  const stopBargeInMonitor = useCallback(() => {
    if (bargeInRafRef.current) {
      cancelAnimationFrame(bargeInRafRef.current);
      bargeInRafRef.current = null;
    }
  }, []);

  const stopPlayback = useCallback(() => {
    audioQueueRef.current = [];
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.src = "";
    }
    isPlayingRef.current = false;
  }, []);

  const resumeListening = useCallback(() => {
    isSendingAudioRef.current = true;
    llmDoneRef.current = false;
    setStatus("listening");
    if (micAnalyserRef.current) setAnalyser(micAnalyserRef.current);
  }, []);

  const playNextAudio = useCallback(() => {
    if (audioQueueRef.current.length === 0) {
      isPlayingRef.current = false;
      if (llmDoneRef.current) {
        // Always-on mode: go back to listening instead of idle
        resumeListening();
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
  }, [resumeListening]);

  useEffect(() => {
    const audio = new Audio();
    audio.crossOrigin = "anonymous";
    audio.onended = playNextAudio;
    audio.onerror = playNextAudio;
    audioRef.current = audio;

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

  const startListening = useCallback(async () => {
    // Clean up any previous session
    stopBargeInMonitor();
    stopPlayback();
    llmDoneRef.current = false;
    setError(null);

    // Close old WebSocket before creating a new one
    if (wsRef.current && wsRef.current.readyState !== WebSocket.CLOSED) {
      wsRef.current.close();
    }

    const handleBargeIn = () => {
      stopBargeInMonitor();
      stopPlayback();
      if (wsRef.current) wsRef.current.close();
      // Restart listening immediately
      setTimeout(() => startListening(), 50);
    };

    const ws = createVoiceStream({
      onVadState: (state: VadState) => {
        // Ignore backend's vad_state "listening" while we're still speaking/streaming -
        // frontend decides when to resume listening (via playNextAudio).
        if (state === "listening") {
          if (statusRef.current === "speaking" || statusRef.current === "streaming") return;
          resumeListening();
        } else if (state === "speech") {
          setStatus("speech");
        } else if (state === "processing") {
          setStatus("processing");
          stopSendingAudio(); // keep mic alive for barge-in
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
          resumeListening();
        }
      },
      onError: (msg) => {
        setError(msg);
        setStatus("error");
        releaseMicrophone();
        setAnalyser(null);
      },
      onPlaySong: (track, url) => {
        options.onPlaySong?.(track, url);
        resumeListening();
      },
      onStopMusic: () => {
        options.onStopMusic?.();
        resumeListening();
      },
      onMusicNotFound: (query) => {
        setError(`Hittade inte: ${query}`);
        resumeListening();
      },
      onLanguageChanged: (lang) => {
        options.onLanguageChanged?.(lang);
      },
    });

    wsRef.current = ws;
    await new Promise<void>((resolve, reject) => {
      ws.onopen = () => resolve();
      ws.onerror = () => reject(new Error("WebSocket failed"));
    });

    try {
      // Reuse existing mic if available, otherwise request new one
      let ctx = audioContextRef.current;
      let stream = streamRef.current;

      if (!stream || !ctx) {
        stream = await navigator.mediaDevices.getUserMedia({
          audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
        });
        streamRef.current = stream;
        ctx = new AudioContext();
        audioContextRef.current = ctx;

        const source = ctx.createMediaStreamSource(stream);
        sourceRef.current = source;

        const micAnalyser = ctx.createAnalyser();
        micAnalyser.fftSize = 128;
        source.connect(micAnalyser);
        micAnalyserRef.current = micAnalyser;
      }

      const inputRate = ctx.sampleRate;
      const targetRate = 16000;

      setAnalyser(micAnalyserRef.current);

      const processor = ctx.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;

      isSendingAudioRef.current = true;

      processor.onaudioprocess = (e) => {
        if (!isSendingAudioRef.current) return;
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

      sourceRef.current!.connect(processor);
      processor.connect(ctx.destination);
      setStatus("listening");

      // Start barge-in monitor loop
      const dataArray = new Uint8Array(micAnalyserRef.current!.frequencyBinCount);
      let loudFrames = 0;

      const monitor = () => {
        const an = micAnalyserRef.current;
        if (!an) return;

        // Only monitor during playback
        if (statusRef.current === "speaking" || statusRef.current === "streaming") {
          an.getByteFrequencyData(dataArray);
          let sum = 0;
          for (let i = 0; i < dataArray.length; i++) sum += dataArray[i];
          const avg = sum / dataArray.length;

          if (avg > BARGE_IN_VOLUME_THRESHOLD) {
            loudFrames++;
            if (loudFrames >= BARGE_IN_FRAMES_REQUIRED) {
              handleBargeIn();
              return;
            }
          } else {
            loudFrames = 0;
          }
        } else {
          loudFrames = 0;
        }

        bargeInRafRef.current = requestAnimationFrame(monitor);
      };
      bargeInRafRef.current = requestAnimationFrame(monitor);
    } catch {
      setError("Kunde inte komma åt mikrofonen.");
      setStatus("error");
      ws.close();
    }
  }, [stopSendingAudio, releaseMicrophone, stopBargeInMonitor, stopPlayback, playNextAudio, options]);

  const handleStop = useCallback(() => {
    if (wsRef.current) stopRecording(wsRef.current);
  }, []);

  useEffect(() => {
    return () => {
      stopBargeInMonitor();
      releaseMicrophone();
    };
  }, [stopBargeInMonitor, releaseMicrophone]);

  const isActive = status !== "idle" && status !== "error";
  const isRecording = status === "listening" || status === "speech";

  return {
    status, error, analyser,
    isActive, isRecording,
    startListening, handleStop,
  };
}
