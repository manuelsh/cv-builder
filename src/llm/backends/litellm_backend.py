"""LiteLLM-backed implementation."""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
from typing import Any


class LiteLLMBackend:
    """Backend that routes calls through LiteLLM."""

    def __init__(self, log_callback: Any | None = None):
        self.log_callback = log_callback

    async def complete(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        """Complete a chat conversation through LiteLLM."""
        input_data = {
            "messages": messages,
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            response = await self._complete_inprocess(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            content = response.choices[0].message.content
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }
        except UnicodeDecodeError:
            content, usage = self._complete_via_subprocess(input_data)

        if self.log_callback:
            output_data = {
                "content": content,
                "usage": usage,
            }
            self.log_callback(input_data, output_data, model)

        return content

    async def _complete_inprocess(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> Any:
        litellm = self._import_litellm()

        return await litellm.acompletion(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def _import_litellm(self) -> Any:
        litellm = importlib.import_module("litellm")
        litellm.drop_params = True
        return litellm

    def _complete_via_subprocess(
        self,
        payload: dict[str, Any],
    ) -> tuple[str, dict[str, int | None]]:
        process = subprocess.run(
            [sys.executable, "-X", "utf8", "-m", "src.llm.litellm_runner"],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            check=False,
        )

        if process.returncode != 0:
            error_message = process.stderr.strip() or "LiteLLM subprocess failed"
            raise RuntimeError(error_message)

        data = json.loads(process.stdout)
        return data["content"], data.get("usage", {})
