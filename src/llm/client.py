"""Provider-agnostic LLM client."""

from __future__ import annotations

from typing import Any

from src.llm.config import get_model, load_config
from src.llm.factory import create_backend


class LLMClient:
    """Client for interacting with LLM backends."""

    def __init__(
        self,
        default_model: str | None = None,
        log_callback: Any | None = None,
        *,
        agent_name: str | None = None,
        backend_name: str | None = None,
        config: dict[str, Any] | None = None,
        backend: Any | None = None,
    ):
        """Initialize the LLM client."""
        self.default_model = default_model
        self.log_callback = log_callback
        self.agent_name = agent_name
        self.backend_name = backend_name
        self.config = config or load_config()
        self._backend = backend

    async def complete(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        """Complete a chat conversation."""
        resolved_model = model or self.default_model
        if resolved_model is None and self.agent_name:
            resolved_model = get_model(
                self.agent_name,
                config=self.config,
                backend_name=self.backend_name,
            )

        if not resolved_model:
            raise ValueError("No model configured")

        backend = self._backend
        if backend is None:
            backend = create_backend(
                backend_name=self.backend_name,
                config=self.config,
                log_callback=self.log_callback,
            )
            self._backend = backend

        return await backend.complete(
            messages=messages,
            model=resolved_model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
