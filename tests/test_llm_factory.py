"""Tests for LLM backend selection and lazy client behavior."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.agents.cv_generator import CVGeneratorAgent
from src.llm.backends import CodexSDKBackend, LiteLLMBackend
from src.llm.client import LLMClient
from src.llm.factory import create_backend


def test_create_backend_defaults_to_litellm():
    """Test that the default backend is LiteLLM."""
    backend = create_backend(config={"llm_backend": "litellm"})
    assert isinstance(backend, LiteLLMBackend)


def test_create_backend_uses_override_over_config():
    """Test that explicit override wins over config default."""
    backend = create_backend(
        backend_name="litellm",
        config={"llm_backend": "codex-sdk"},
    )
    assert isinstance(backend, LiteLLMBackend)


def test_create_backend_can_build_codex_backend():
    """Test creating the Codex backend."""
    backend = create_backend(config={"llm_backend": "codex-sdk"})
    assert isinstance(backend, CodexSDKBackend)


@pytest.mark.asyncio
async def test_llm_client_creates_backend_lazily(monkeypatch):
    """Test that the backend is not created until complete() is called."""
    fake_backend = SimpleNamespace(complete=AsyncMock(return_value="ok"))
    create_backend_calls = []

    def fake_create_backend(*args, **kwargs):
        create_backend_calls.append((args, kwargs))
        return fake_backend

    monkeypatch.setattr("src.llm.client.create_backend", fake_create_backend)

    client = LLMClient(
        agent_name="job_analyzer",
        config={
            "llm_backend": "litellm",
            "model_fast": "test-model-fast",
            "agent_models": {
                "job_analyzer": "fast",
                "cv_generator": "best",
            },
        },
    )

    assert create_backend_calls == []

    result = await client.complete([{"role": "user", "content": "hello"}])

    assert result == "ok"
    assert len(create_backend_calls) == 1


def test_llm_backed_agent_instantiation_is_safe_without_model_env():
    """Test that helper-method tests can instantiate LLM-backed agents safely."""
    agent = CVGeneratorAgent(
        config={
            "llm_backend": "litellm",
            "agent_models": {
                "job_analyzer": "fast",
                "cv_generator": "best",
            },
        }
    )

    assert agent.llm_client is not None
