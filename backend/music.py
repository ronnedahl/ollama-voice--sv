"""
Music library: scan a directory, index audio files with metadata,
search by query, and detect voice commands.
"""

import os
import re
from dataclasses import dataclass, asdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

from mutagen import File as MutagenFile

SUPPORTED_EXTENSIONS = {".mp3", ".m4a", ".flac", ".wav", ".ogg"}


@dataclass
class Track:
    id: str
    filename: str
    title: str
    artist: str
    path: str

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("path")  # Don't expose filesystem path
        return d


def _read_metadata(path: Path) -> tuple[str, str]:
    """Extract title and artist from audio file. Falls back to filename."""
    try:
        audio = MutagenFile(path, easy=True)
        if audio:
            title = (audio.get("title", [None])[0]) or path.stem
            artist = (audio.get("artist", [None])[0]) or "Unknown"
            return title, artist
    except Exception:
        pass
    return path.stem, "Unknown"


class MusicLibrary:
    def __init__(self, music_dir: str):
        self.music_dir = Path(music_dir)
        self.tracks: list[Track] = []

    def scan(self) -> int:
        """Scan music directory and build index. Returns track count."""
        self.tracks = []
        if not self.music_dir.exists():
            print(f"Music directory not found: {self.music_dir}")
            return 0

        for path in sorted(self.music_dir.rglob("*")):
            if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            title, artist = _read_metadata(path)
            track_id = str(len(self.tracks))
            self.tracks.append(Track(
                id=track_id,
                filename=path.name,
                title=title,
                artist=artist,
                path=str(path),
            ))

        print(f"Music library: indexed {len(self.tracks)} tracks from {self.music_dir}")
        return len(self.tracks)

    def search(self, query: str) -> Optional[Track]:
        """Find best matching track by title, artist, or filename."""
        if not self.tracks or not query.strip():
            return None

        query_lower = query.lower().strip()

        # 1. Exact substring match in title
        for track in self.tracks:
            if query_lower in track.title.lower():
                return track

        # 2. Exact substring in artist
        for track in self.tracks:
            if query_lower in track.artist.lower():
                return track

        # 3. Substring in filename
        for track in self.tracks:
            if query_lower in track.filename.lower():
                return track

        # 4. Fuzzy match on title (best similarity score)
        best_score = 0.0
        best_track = None
        for track in self.tracks:
            score = SequenceMatcher(None, query_lower, track.title.lower()).ratio()
            if score > best_score:
                best_score = score
                best_track = track

        return best_track if best_score > 0.4 else None

    def get(self, track_id: str) -> Optional[Track]:
        for track in self.tracks:
            if track.id == track_id:
                return track
        return None


# Voice command patterns (Swedish + English)
PLAY_PATTERN = re.compile(
    r"\b(?:spela|sätt på|kör|play|put on)(?:\s+(?:låten|the song))?\s+(.+?)(?:\s*[.!?]|$)",
    re.IGNORECASE,
)

STOP_PATTERN = re.compile(
    r"\b(?:stoppa|pausa|stäng av|avsluta|stop|pause)\s+(?:musiken|låten|musik|the music|the song|music)",
    re.IGNORECASE,
)


def detect_play_command(text: str) -> Optional[str]:
    """Return search query if text is a 'play song' command, else None."""
    match = PLAY_PATTERN.search(text)
    if match:
        return match.group(1).strip()
    return None


def detect_stop_command(text: str) -> bool:
    """Return True if text is a 'stop music' command."""
    return bool(STOP_PATTERN.search(text))
