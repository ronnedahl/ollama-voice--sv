"""In-memory conversation history (last N turn pairs)."""

from collections import deque
from threading import Lock

MAX_TURNS = 6


class ConversationMemory:
    """Keeps the last `max_turns` user/assistant pairs in process memory."""

    def __init__(self, max_turns: int = MAX_TURNS):
        self._turns: deque[tuple[str, str]] = deque(maxlen=max_turns)
        self._lock = Lock()

    def as_messages(self) -> list[dict]:
        with self._lock:
            messages: list[dict] = []
            for user, assistant in self._turns:
                messages.append({"role": "user", "content": user})
                messages.append({"role": "assistant", "content": assistant})
            return messages

    def add_turn(self, user: str, assistant: str) -> None:
        if not user.strip() or not assistant.strip():
            return
        with self._lock:
            self._turns.append((user, assistant))

    def clear(self) -> None:
        with self._lock:
            self._turns.clear()
