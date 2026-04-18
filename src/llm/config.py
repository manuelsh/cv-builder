"""LLM configuration utilities."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Load .env file
load_dotenv()

SUPPORTED_BACKENDS = {"litellm", "codex-sdk"}


def get_project_root() -> Path:
    """Return the repository root."""
    return Path(__file__).resolve().parents[2]


def get_codex_bridge_dir() -> Path:
    """Return the Codex bridge directory."""
    return get_project_root() / "codex_bridge"


def get_codex_auth_file() -> Path:
    """Return the default Codex auth file path."""
    return Path.home() / ".codex" / "auth.json"


def load_config(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    """Load configuration from environment variables."""
    config = {
        "aws_region": os.getenv("AWS_REGION", "eu-west-1"),
        "model_fast": os.getenv("BEDROCK_MODEL_FAST"),
        "model_best": os.getenv("BEDROCK_MODEL_BEST"),
        "codex_model_fast": os.getenv("CODEX_MODEL_FAST"),
        "codex_model_best": os.getenv("CODEX_MODEL_BEST"),
        "codex_node_bin": os.getenv("CODEX_NODE_BIN", "node"),
        "llm_backend": os.getenv("CV_BUILDER_LLM_BACKEND", "litellm"),
        "output_path": os.getenv("CV_BUILDER_OUTPUT_PATH"),
        "agent_models": {
            "job_analyzer": "fast",
            "cv_generator": "best",
        },
    }

    if overrides:
        config.update(overrides)

    return config


def get_backend_name(
    config: dict[str, Any] | None = None,
    override: str | None = None,
) -> str:
    """Resolve the active LLM backend name."""
    if config is None:
        config = load_config()

    backend_name = override or config.get("llm_backend", "litellm")
    if backend_name not in SUPPORTED_BACKENDS:
        raise ValueError(
            f"Invalid LLM backend '{backend_name}'. "
            f"Must be one of: {sorted(SUPPORTED_BACKENDS)}"
        )

    return backend_name


def get_model(
    agent_name: str,
    config: dict[str, Any] | None = None,
    backend_name: str | None = None,
) -> str:
    """Get the configured model for an agent and backend."""
    if config is None:
        config = load_config()

    resolved_backend = get_backend_name(config=config, override=backend_name)
    agent_models = config.get("agent_models", {})
    model_type = agent_models.get(agent_name, "fast")

    if resolved_backend == "codex-sdk":
        if model_type == "best":
            model = config.get("codex_model_best")
        else:
            model = config.get("codex_model_fast")

        env_key = f"CODEX_MODEL_{model_type.upper()}"
    else:
        if model_type == "best":
            model = config.get("model_best")
        else:
            model = config.get("model_fast")

        env_key = f"BEDROCK_MODEL_{model_type.upper()}"

    if not model:
        raise ValueError(
            f"Model not configured for {agent_name}. Set {env_key} in .env"
        )

    if resolved_backend == "litellm" and model.startswith("arn:aws:bedrock"):
        if "application-inference-profile" in model:
            if not model.startswith("bedrock/converse/"):
                model = f"bedrock/converse/{model}"
        elif not model.startswith("bedrock/"):
            model = f"bedrock/{model}"

    return model


def validate_backend_prerequisites(
    backend_name: str | None = None,
    config: dict[str, Any] | None = None,
) -> tuple[list[str], list[str]]:
    """Return backend validation errors and warnings."""
    if config is None:
        config = load_config()

    resolved_backend = get_backend_name(config=config, override=backend_name)

    if resolved_backend == "codex-sdk":
        return _validate_codex_backend(config)

    return _validate_litellm_backend(config)


def get_output_path(config: dict[str, Any] | None = None) -> Path | None:
    """Get the output path from config."""
    if config is None:
        config = load_config()

    path_str = config.get("output_path")
    if path_str:
        return Path(path_str)
    return None


def _validate_litellm_backend(
    config: dict[str, Any],
) -> tuple[list[str], list[str]]:
    errors: list[str] = []

    if not config.get("model_fast"):
        errors.append("Missing BEDROCK_MODEL_FAST in environment")
    if not config.get("model_best"):
        errors.append("Missing BEDROCK_MODEL_BEST in environment")

    import_check = subprocess.run(
        [sys.executable, "-X", "utf8", "-c", "import litellm"],
        capture_output=True,
        text=True,
        check=False,
    )
    if import_check.returncode != 0:
        stderr = import_check.stderr.strip() or "Unknown import error"
        errors.append(f"LiteLLM import check failed: {stderr}")

    return errors, []


def _validate_codex_backend(
    config: dict[str, Any],
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    if not config.get("codex_model_fast"):
        errors.append("Missing CODEX_MODEL_FAST in environment")
    if not config.get("codex_model_best"):
        errors.append("Missing CODEX_MODEL_BEST in environment")

    node_bin = config.get("codex_node_bin", "node")
    node_path = shutil.which(node_bin)
    if not node_path:
        errors.append(f"Node.js executable not found: {node_bin}")
        return errors, warnings

    version_check = subprocess.run(
        [node_bin, "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    if version_check.returncode != 0:
        stderr = version_check.stderr.strip() or "Unknown Node.js error"
        errors.append(f"Failed to run Node.js version check: {stderr}")
    else:
        major = _parse_node_major(version_check.stdout.strip())
        if major is None or major < 18:
            errors.append(
                f"Node.js 18+ is required for Codex SDK; found {version_check.stdout.strip()}"
            )

    bridge_dir = get_codex_bridge_dir()
    if not (bridge_dir / "package.json").exists():
        errors.append("Missing codex_bridge/package.json")
    if not (bridge_dir / "runner.mjs").exists():
        errors.append("Missing codex_bridge/runner.mjs")
    if not (bridge_dir / "node_modules" / "@openai" / "codex-sdk" / "package.json").exists():
        errors.append(
            "Codex bridge dependencies are not installed. Run 'npm install --prefix codex_bridge'."
        )

    auth_file = get_codex_auth_file()
    if not any(os.getenv(key) for key in ("OPENAI_API_KEY", "CODEX_API_KEY")) and not auth_file.exists():
        warnings.append(
            "Codex authentication could not be verified automatically. "
            "Set OPENAI_API_KEY/CODEX_API_KEY or sign in with the local Codex CLI."
        )

    return errors, warnings


def _parse_node_major(version_output: str) -> int | None:
    normalized = version_output.lstrip("v")
    try:
        return int(normalized.split(".", maxsplit=1)[0])
    except (TypeError, ValueError):
        return None
