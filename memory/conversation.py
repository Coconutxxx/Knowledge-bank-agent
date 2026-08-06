"""仅保存用户与最终回答，避免把冗长工具结果长期塞进上下文。"""

from __future__ import annotations

from collections import deque


class ConversationMemory:
    def __init__(self, max_turns: int = 8):
        self.max_turns = max_turns
        self._messages: deque[dict[str, str]] = deque(maxlen=max_turns * 2)

    def add_turn(self, user_message: str, assistant_message: str) -> None:
        self._messages.append({"role": "user", "content": user_message})
        self._messages.append({"role": "assistant", "content": assistant_message})

    def messages(self) -> list[dict[str, str]]:
        return list(self._messages)

    def clear(self) -> None:
        self._messages.clear()

