"""Shared singletons initialised on first import."""

from config import MUSIC_DIR
from music import MusicLibrary

music_library = MusicLibrary(MUSIC_DIR)
