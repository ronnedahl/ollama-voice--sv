"use client";

import { useEffect, useRef } from "react";

interface AudioPlayerProps {
  audioBlob: Blob | null;
  autoPlay?: boolean;
  onPlaybackEnd?: () => void;
}

export default function AudioPlayer({ audioBlob, autoPlay = true, onPlaybackEnd }: AudioPlayerProps) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const urlRef = useRef<string | null>(null);

  useEffect(() => {
    if (urlRef.current) {
      URL.revokeObjectURL(urlRef.current);
      urlRef.current = null;
    }

    if (audioBlob && audioRef.current) {
      const url = URL.createObjectURL(audioBlob);
      urlRef.current = url;
      audioRef.current.src = url;

      if (autoPlay) {
        audioRef.current.play().catch(console.error);
      }
    }

    return () => {
      if (urlRef.current) {
        URL.revokeObjectURL(urlRef.current);
      }
    };
  }, [audioBlob, autoPlay]);

  if (!audioBlob) return null;

  return (
    <div className="audio-player">
      <audio
        ref={audioRef}
        controls
        onEnded={onPlaybackEnd}
      />

      <style jsx>{`
        .audio-player {
          width: 100%;
          max-width: 400px;
        }

        audio {
          width: 100%;
          border-radius: 8px;
        }
      `}</style>
    </div>
  );
}
