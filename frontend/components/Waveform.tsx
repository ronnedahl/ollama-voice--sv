"use client";

import { useEffect, useRef } from "react";
import { Status } from "@/hooks/useVoicePipeline";

interface WaveformProps {
  status: Status;
  analyser: AnalyserNode | null;
  onClick: () => void;
}

const BAR_COUNT = 48;

export default function Waveform({ status, analyser, onClick }: WaveformProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      canvas.width = rect.width * dpr;
      canvas.height = rect.height * dpr;
      ctx.scale(dpr, dpr);
    };
    resize();
    window.addEventListener("resize", resize);

    let phase = 0;
    const dataArray = analyser ? new Uint8Array(analyser.frequencyBinCount) : null;

    const draw = () => {
      const rect = canvas.getBoundingClientRect();
      const w = rect.width;
      const h = rect.height;
      ctx.clearRect(0, 0, w, h);

      // Get audio data or generate idle animation
      const bars: number[] = [];
      if (analyser && dataArray) {
        analyser.getByteFrequencyData(dataArray);
        const step = Math.floor(dataArray.length / BAR_COUNT);
        for (let i = 0; i < BAR_COUNT; i++) {
          bars.push(dataArray[i * step] / 255);
        }
      } else {
        // Idle animation - subtle sine wave
        phase += 0.05;
        for (let i = 0; i < BAR_COUNT; i++) {
          const v = Math.sin(phase + i * 0.3) * 0.15 + 0.2;
          bars.push(Math.max(0.05, v));
        }
      }

      const barWidth = w / BAR_COUNT;
      const gap = barWidth * 0.4;
      const actualBarWidth = barWidth - gap;
      const centerY = h / 2;
      const maxHeight = h * 0.85;

      // Color based on status
      const colors: Record<Status, [string, string]> = {
        idle: ["#0ea5e9", "#06b6d4"],
        listening: ["#3b82f6", "#06b6d4"],
        speech: ["#10b981", "#34d399"],
        processing: ["#8b5cf6", "#a78bfa"],
        streaming: ["#8b5cf6", "#a78bfa"],
        speaking: ["#06b6d4", "#22d3ee"],
        error: ["#ef4444", "#f87171"],
      };
      const [c1, c2] = colors[status];

      bars.forEach((v, i) => {
        const barHeight = Math.max(4, v * maxHeight);
        const x = i * barWidth + gap / 2;
        const y = centerY - barHeight / 2;

        const gradient = ctx.createLinearGradient(0, y, 0, y + barHeight);
        gradient.addColorStop(0, c1);
        gradient.addColorStop(1, c2);
        ctx.fillStyle = gradient;
        ctx.shadowColor = c1;
        ctx.shadowBlur = 12;

        const radius = actualBarWidth / 2;
        ctx.beginPath();
        ctx.roundRect(x, y, actualBarWidth, barHeight, radius);
        ctx.fill();
      });

      rafRef.current = requestAnimationFrame(draw);
    };

    draw();

    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      window.removeEventListener("resize", resize);
    };
  }, [status, analyser]);

  return (
    <button
      onClick={onClick}
      className="group relative w-full max-w-xl h-48 md:h-56 cursor-pointer focus:outline-none"
      aria-label="Tryck för att prata"
    >
      <canvas ref={canvasRef} className="w-full h-full" />
    </button>
  );
}
