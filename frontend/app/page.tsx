"use client";

import { useEffect, useState } from "react";
import { useVoicePipeline, Status } from "@/hooks/useVoicePipeline";
import { useMusicPlayer } from "@/hooks/useMusicPlayer";
import { Language, getLanguage, setLanguage as setLanguageApi } from "@/lib/api";
import Waveform from "@/components/Waveform";
import StatusLabel from "@/components/StatusLabel";
import NowPlaying from "@/components/NowPlaying";
import LanguageToggle from "@/components/LanguageToggle";

const statusToValue: Record<Status, string> = {
  idle: "READY",
  listening: "LISTENING",
  speech: "RECORDING",
  processing: "THINKING",
  streaming: "RESPONDING",
  speaking: "SPEAKING",
  error: "ERROR",
};

export default function Home() {
  const music = useMusicPlayer();
  const [language, setLanguage] = useState<Language>("en");
  const [languagePending, setLanguagePending] = useState(false);

  useEffect(() => {
    getLanguage().then(setLanguage).catch(() => {});
  }, []);

  const { status, error, analyser, isRecording, startListening, handleStop } = useVoicePipeline({
    onPlaySong: (track, url) => music.play(track, url),
    onStopMusic: () => music.stop(),
    onLanguageChanged: (lang) => setLanguage(lang),
  });

  const handleClick = () => {
    if (isRecording) handleStop();
    else if (status === "idle" || status === "error") startListening();
  };

  const handleLanguageToggle = async () => {
    const next: Language = language === "en" ? "sv" : "en";
    setLanguagePending(true);
    try {
      const updated = await setLanguageApi(next);
      setLanguage(updated);
    } catch (e) {
      console.error("Language switch failed:", e);
    } finally {
      setLanguagePending(false);
    }
  };

  return (
    <main className="relative h-dvh w-full overflow-hidden flex flex-col">
      {/* Top labels */}
      <header className="flex justify-between items-start px-6 md:px-10 pt-6 md:pt-10">
        <LanguageToggle
          language={language}
          onToggle={handleLanguageToggle}
          disabled={languagePending}
        />
        <StatusLabel label="Status" value={statusToValue[status]} align="right" />
      </header>

      {/* Center content */}
      <div className="flex-1 flex flex-col items-center justify-center gap-8 px-6">
        <Waveform status={status} analyser={analyser} onClick={handleClick} />

        <div className="text-center space-y-2">
          <h1 className="text-2xl md:text-4xl font-light tracking-[0.15em] text-white">
            AI VOICE ASSISTANT
          </h1>
          <p className="text-xs md:text-sm text-slate-500 tracking-wider">
            {status === "idle" ? "TAP TO SPEAK" : statusToValue[status]}
          </p>
        </div>

        {music.currentTrack && (
          <NowPlaying
            track={music.currentTrack}
            isPlaying={music.isPlaying}
            onStop={music.stop}
          />
        )}

        {error && (
          <div className="text-red-400 text-sm bg-red-500/10 border border-red-500/20 px-4 py-2 rounded-lg">
            {error}
          </div>
        )}
      </div>

      {/* Bottom subtle gradient */}
      <div className="absolute bottom-0 left-0 right-0 h-32 bg-gradient-to-t from-black to-transparent pointer-events-none" />
    </main>
  );
}
