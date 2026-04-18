"""UTF-8 subprocess runner for LiteLLM calls on Windows."""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any


async def _run_completion(payload: dict[str, Any]) -> dict[str, Any]:
    import litellm

    litellm.drop_params = True

    response = await litellm.acompletion(
        model=payload["model"],
        messages=payload["messages"],
        temperature=payload["temperature"],
        max_tokens=payload["max_tokens"],
    )

    return {
        "content": response.choices[0].message.content,
        "usage": {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens,
        },
    }


def main() -> int:
    """Read a request from stdin and write the response to stdout."""
    try:
        payload = json.loads(sys.stdin.read())
        result = asyncio.run(_run_completion(payload))
        print(json.dumps(result))
        return 0
    except Exception as exc:  # pragma: no cover - exercised via subprocess
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
