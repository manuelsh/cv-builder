"""Tests for the LiteLLM backend."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.llm.backends.litellm_backend import LiteLLMBackend


def _fake_response(content: str = "hello") -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
        ),
    )


@pytest.mark.asyncio
async def test_complete_uses_inprocess_litellm(monkeypatch):
    """Test normal in-process LiteLLM completion."""
    backend = LiteLLMBackend()
    fake_module = SimpleNamespace(acompletion=AsyncMock(return_value=_fake_response("inprocess")))

    monkeypatch.setattr(backend, "_import_litellm", lambda: fake_module)

    result = await backend.complete(
        messages=[{"role": "user", "content": "hi"}],
        model="test-model",
    )

    assert result == "inprocess"
    fake_module.acompletion.assert_awaited_once()


@pytest.mark.asyncio
async def test_complete_falls_back_to_subprocess_on_unicode_error(monkeypatch):
    """Test subprocess fallback for Windows LiteLLM import issues."""
    backend = LiteLLMBackend()

    monkeypatch.setattr(
        backend,
        "_complete_inprocess",
        AsyncMock(side_effect=UnicodeDecodeError("cp1252", b"\x81", 0, 1, "boom")),
    )
    subprocess_fallback = MagicMock(return_value=("fallback", {"total_tokens": 12}))
    monkeypatch.setattr(backend, "_complete_via_subprocess", subprocess_fallback)

    result = await backend.complete(
        messages=[{"role": "user", "content": "hi"}],
        model="test-model",
    )

    assert result == "fallback"
    subprocess_fallback.assert_called_once()


@pytest.mark.asyncio
async def test_complete_logs_usage(monkeypatch):
    """Test log callback on successful completion."""
    logger = MagicMock()
    backend = LiteLLMBackend(log_callback=logger)
    fake_module = SimpleNamespace(acompletion=AsyncMock(return_value=_fake_response("logged")))

    monkeypatch.setattr(backend, "_import_litellm", lambda: fake_module)

    await backend.complete(
        messages=[{"role": "user", "content": "hi"}],
        model="test-model",
    )

    logger.assert_called_once()
