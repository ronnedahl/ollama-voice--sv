import { Track } from "@/lib/api";

interface NowPlayingProps {
  track: Track;
  isPlaying: boolean;
  onStop: () => void;
}

const MusicIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M9 18V5l12-2v13" />
    <circle cx="6" cy="18" r="3" />
    <circle cx="18" cy="16" r="3" />
  </svg>
);

const StopIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <rect x="6" y="6" width="12" height="12" rx="1" />
  </svg>
);

export default function NowPlaying({ track, isPlaying, onStop }: NowPlayingProps) {
  return (
    <div className="flex items-center gap-3 px-4 py-3 bg-white/5 border border-white/10 rounded-xl backdrop-blur-sm max-w-md w-full">
      <div className={`w-10 h-10 rounded-lg bg-cyan-500/20 text-cyan-400 flex items-center justify-center shrink-0 ${isPlaying ? "animate-pulse" : ""}`}>
        <MusicIcon />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-white truncate">{track.title}</p>
        <p className="text-xs text-slate-500 truncate">{track.artist}</p>
      </div>
      <button
        onClick={onStop}
        className="flex items-center gap-2 px-4 py-2 rounded-lg bg-red-500/20 hover:bg-red-500/30 text-red-300 border border-red-500/30 text-sm font-medium tracking-wider transition-colors shrink-0"
        aria-label="Stop music"
      >
        <StopIcon />
        STOP
      </button>
    </div>
  );
}
