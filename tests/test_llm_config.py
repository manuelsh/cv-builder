"""Tests for LLM config and backend prerequisite validation."""

import subprocess

from src.llm.config import (
    get_backend_name,
    get_model,
    load_config,
    validate_backend_prerequisites,
)


def test_get_backend_name_defaults_to_litellm(monkeypatch):
    """Test backend default resolution."""
    monkeypatch.delenv("CV_BUILDER_LLM_BACKEND", raising=False)

    config = load_config()
    assert get_backend_name(config=config) == "litellm"


def test_get_backend_name_honors_override():
    """Test explicit backend override."""
    assert get_backend_name(config={"llm_backend": "litellm"}, override="codex-sdk") == "codex-sdk"


def test_get_model_uses_codex_model_mapping():
    """Test Codex model resolution by agent tier."""
    config = {
        "llm_backend": "codex-sdk",
        "codex_model_fast": "gpt-5.4-mini",
        "codex_model_best": "gpt-5.4",
        "agent_models": {
            "job_analyzer": "fast",
            "cv_generator": "best",
        },
    }

    assert get_model("job_analyzer", config=config) == "gpt-5.4-mini"
    assert get_model("cv_generator", config=config) == "gpt-5.4"


def test_validate_litellm_backend_checks_env_and_import(monkeypatch):
    """Test LiteLLM backend validation."""
    monkeypatch.setattr(
        "src.llm.config.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, "", ""),
    )

    errors, warnings = validate_backend_prerequisites(
        backend_name="litellm",
        config={
            "llm_backend": "litellm",
            "model_fast": "arn:aws:bedrock:fast",
            "model_best": "arn:aws:bedrock:best",
        },
    )

    assert errors == []
    assert warnings == []


def test_validate_codex_backend_reports_missing_install(monkeypatch, tmp_path):
    """Test Codex backend validation when bridge deps are missing."""
    bridge_dir = tmp_path / "codex_bridge"
    bridge_dir.mkdir()
    (bridge_dir / "package.json").write_text("{}", encoding="utf-8")
    (bridge_dir / "runner.mjs").write_text("console.log('ok')", encoding="utf-8")

    auth_file = tmp_path / "auth.json"
    auth_file.write_text("{}", encoding="utf-8")

    monkeypatch.setattr("src.llm.config.get_codex_bridge_dir", lambda: bridge_dir)
    monkeypatch.setattr("src.llm.config.get_codex_auth_file", lambda: auth_file)
    monkeypatch.setattr("src.llm.config.shutil.which", lambda name: "C:/node.exe")
    monkeypatch.setattr(
        "src.llm.config.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, "v22.9.0", ""),
    )

    errors, warnings = validate_backend_prerequisites(
        backend_name="codex-sdk",
        config={
            "llm_backend": "codex-sdk",
            "codex_model_fast": "gpt-5.4-mini",
            "codex_model_best": "gpt-5.4",
            "codex_node_bin": "node",
        },
    )

    assert "Codex bridge dependencies are not installed. Run 'npm install --prefix codex_bridge'." in errors
    assert warnings == []


def test_validate_codex_backend_warns_when_auth_cannot_be_verified(monkeypatch, tmp_path):
    """Test Codex backend validation warning for auth verification."""
    bridge_dir = tmp_path / "codex_bridge"
    sdk_dir = bridge_dir / "node_modules" / "@openai" / "codex-sdk"
    sdk_dir.mkdir(parents=True)
    (bridge_dir / "package.json").write_text("{}", encoding="utf-8")
    (bridge_dir / "runner.mjs").write_text("console.log('ok')", encoding="utf-8")
    (sdk_dir / "package.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr("src.llm.config.get_codex_bridge_dir", lambda: bridge_dir)
    monkeypatch.setattr("src.llm.config.get_codex_auth_file", lambda: tmp_path / "missing-auth.json")
    monkeypatch.setattr("src.llm.config.shutil.which", lambda name: "C:/node.exe")
    monkeypatch.setattr(
        "src.llm.config.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, "v22.9.0", ""),
    )
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("CODEX_API_KEY", raising=False)

    errors, warnings = validate_backend_prerequisites(
        backend_name="codex-sdk",
        config={
            "llm_backend": "codex-sdk",
            "codex_model_fast": "gpt-5.4-mini",
            "codex_model_best": "gpt-5.4",
            "codex_node_bin": "node",
        },
    )

    assert errors == []
    assert warnings == [
        "Codex authentication could not be verified automatically. "
        "Set OPENAI_API_KEY/CODEX_API_KEY or sign in with the local Codex CLI."
    ]
