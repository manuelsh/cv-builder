"""Shared LLM backend types."""

from typing import Any, Protocol


class LLMBackend(Protocol):
    """Protocol implemented by concrete LLM backends."""

    async def complete(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        """Return the assistant response text."""

