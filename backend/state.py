"""Shared singletons initialised on first import."""

from config import LANGUAGE, MUSIC_DIR
from music import MusicLibrary
from services.language import LanguageState
from services.memory import ConversationMemory

music_library = MusicLibrary(MUSIC_DIR)
conversation_memory = ConversationMemory()
language_state = LanguageState(LANGUAGE)
