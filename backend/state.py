"""Shared singletons initialised on first import."""

from config import MUSIC_DIR
from music import MusicLibrary
from services.memory import ConversationMemory

music_library = MusicLibrary(MUSIC_DIR)
conversation_memory = ConversationMemory()
