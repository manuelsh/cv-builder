"""Codex SDK-backed implementation."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from src.llm.config import get_codex_bridge_dir


class CodexSDKBackend:
    """Backend that delegates completions to the Codex SDK bridge."""

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        log_callback: Any | None = None,
    ):
        self.config = config or {}
        self.log_callback = log_callback

    async def complete(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        """Complete a conversation through the Codex SDK bridge."""
        prompt = self._build_prompt(messages)
        payload = {
            "prompt": prompt,
            "model": model,
            "cwd": str(Path.cwd()),
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        runner_path = self._bridge_runner_path()
        node_bin = self.config.get("codex_node_bin", "node")

        process = subprocess.run(
            [node_bin, str(runner_path)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            check=False,
            cwd=Path.cwd(),
        )

        if process.returncode != 0:
            error_message = process.stderr.strip() or "Codex SDK bridge failed"
            raise RuntimeError(error_message)

        data = json.loads(process.stdout)
        content = data["content"]

        if self.log_callback:
            self.log_callback(
                payload,
                {"content": content, "usage": data.get("usage")},
                model,
            )

        return content

    def _bridge_runner_path(self) -> Path:
        return get_codex_bridge_dir() / "runner.mjs"

    def _build_prompt(self, messages: list[dict[str, str]]) -> str:
        parts = [
            "You are continuing this conversation transcript.",
            "Respond as the assistant to the latest user request.",
            "Preserve any output formatting and schema requirements from the transcript.",
            "Do not inspect the local repository or use tools unless the transcript explicitly requires it.",
            "Answer directly from the provided transcript.",
            "",
        ]

        for message in messages:
            role = message.get("role", "user").upper()
            content = message.get("content", "").strip()
            parts.append(f"<{role}>")
            parts.append(content)
            parts.append(f"</{role}>")
            parts.append("")

        return "\n".join(parts).strip()
