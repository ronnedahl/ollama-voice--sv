"""Runtime language state (en/sv), thread-safe."""

from threading import Lock

SUPPORTED = ("en", "sv")


class UnsupportedLanguageError(ValueError):
    """Raised when a non-supported language code is set."""


class LanguageState:
    """Thread-safe holder for the currently-active language code."""

    def __init__(self, initial: str):
        self._validate(initial)
        self._language = initial
        self._lock = Lock()

    @staticmethod
    def _validate(language: str) -> None:
        if language not in SUPPORTED:
            raise UnsupportedLanguageError(
                f"Unsupported language {language!r}; expected one of {SUPPORTED}"
            )

    def get(self) -> str:
        with self._lock:
            return self._language

    def set(self, language: str) -> None:
        self._validate(language)
        with self._lock:
            self._language = language
