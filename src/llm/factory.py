"""Factory helpers for LLM backends."""

from __future__ import annotations

from typing import Any

from src.llm.backends import CodexSDKBackend, LiteLLMBackend, LLMBackend
from src.llm.config import get_backend_name


def create_backend(
    backend_name: str | None = None,
    config: dict[str, Any] | None = None,
    log_callback: Any | None = None,
) -> LLMBackend:
    """Create an LLM backend implementation."""
    resolved_backend = get_backend_name(config=config, override=backend_name)

    if resolved_backend == "litellm":
        return LiteLLMBackend(log_callback=log_callback)
    if resolved_backend == "codex-sdk":
        return CodexSDKBackend(config=config, log_callback=log_callback)

    raise ValueError(f"Unsupported LLM backend: {resolved_backend}")
