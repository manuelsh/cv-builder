"""Tests for the Codex SDK backend."""

import json
import subprocess
from pathlib import Path

import pytest

from src.llm.backends.codex_backend import CodexSDKBackend


def test_build_prompt_includes_roles():
    """Test prompt serialization for Codex."""
    backend = CodexSDKBackend()
    prompt = backend._build_prompt(
        [
            {"role": "system", "content": "Return JSON"},
            {"role": "user", "content": "Say hello"},
        ]
    )

    assert "<SYSTEM>" in prompt
    assert "<USER>" in prompt
    assert "Return JSON" in prompt
    assert "Say hello" in prompt


@pytest.mark.asyncio
async def test_complete_invokes_bridge(monkeypatch):
    """Test bridge invocation and response parsing."""
    backend = CodexSDKBackend(config={"codex_node_bin": "node"})

    monkeypatch.setattr(
        backend,
        "_bridge_runner_path",
        lambda: Path("codex_bridge") / "runner.mjs",
    )
    monkeypatch.setattr(
        "src.llm.backends.codex_backend.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0],
            0,
            stdout=json.dumps({"content": "codex output", "usage": {"total_tokens": 7}}),
            stderr="",
        ),
    )

    result = await backend.complete(
        messages=[{"role": "user", "content": "hello"}],
        model="gpt-5.4",
    )

    assert result == "codex output"


@pytest.mark.asyncio
async def test_complete_raises_on_bridge_error(monkeypatch):
    """Test bridge failure propagation."""
    backend = CodexSDKBackend(config={"codex_node_bin": "node"})

    monkeypatch.setattr(
        "src.llm.backends.codex_backend.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0],
            1,
            stdout="",
            stderr="bridge exploded",
        ),
    )

    with pytest.raises(RuntimeError, match="bridge exploded"):
        await backend.complete(
            messages=[{"role": "user", "content": "hello"}],
            model="gpt-5.4",
        )
