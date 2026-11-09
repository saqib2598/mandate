"""In-memory message bus. Only messages the guard allowed are appended."""
from __future__ import annotations


class Bus:
    def __init__(self):
        self.messages: list[dict] = []

    def append(self, message: dict) -> None:
        self.messages.append(message)

    def pending_for(self, role: str, already: int) -> list[dict]:
        return [m for m in self.messages[already:] if m.get("target") in (role, "broadcast", "*", "all")]
