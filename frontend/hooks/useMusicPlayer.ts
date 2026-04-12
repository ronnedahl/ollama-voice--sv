"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Track, API_BASE_URL } from "@/lib/api";

export function useMusicPlayer() {
  const [currentTrack, setCurrentTrack] = useState<Track | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    const audio = new Audio();
    audio.onplay = () => setIsPlaying(true);
    audio.onpause = () => setIsPlaying(false);
    audio.onended = () => {
      setIsPlaying(false);
      setCurrentTrack(null);
    };
    audioRef.current = audio;

    return () => {
      audio.pause();
      audio.src = "";
    };
  }, []);

  const play = useCallback((track: Track, url: string) => {
    if (!audioRef.current) return;
    audioRef.current.src = `${API_BASE_URL}${url}`;
    audioRef.current.play().catch(console.error);
    setCurrentTrack(track);
  }, []);

  const stop = useCallback(() => {
    if (!audioRef.current) return;
    audioRef.current.pause();
    audioRef.current.currentTime = 0;
    setCurrentTrack(null);
    setIsPlaying(false);
  }, []);

  return { currentTrack, isPlaying, play, stop };
}
