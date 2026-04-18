"""Tests for Google Drive OAuth authentication."""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestGetCredentials:
    """Tests for get_credentials function."""

    @pytest.fixture
    def mock_credentials(self):
        """Create mock credentials."""
        creds = MagicMock()
        creds.valid = True
        creds.expired = False
        creds.refresh_token = "refresh_token"
        creds.to_json.return_value = '{"token": "test"}'
        return creds

    @pytest.fixture
    def sample_client_config(self):
        """Sample OAuth client configuration."""
        return {
            "installed": {
                "client_id": "test_client_id",
                "client_secret": "test_client_secret",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost"],
            }
        }

    def test_loads_existing_valid_token(self, mock_credentials, tmp_path):
        """Test loading existing valid token from file."""
        token_path = tmp_path / "token.json"
        token_path.write_text('{"token": "existing"}')

        with patch("src.google_drive.auth.TOKEN_PATH", token_path), \
             patch("src.google_drive.auth.Credentials") as MockCreds:
            MockCreds.from_authorized_user_file.return_value = mock_credentials

            from src.google_drive.auth import get_credentials
            creds = get_credentials()

            MockCreds.from_authorized_user_file.assert_called_once()
            assert creds == mock_credentials

    def test_refreshes_expired_token(self, mock_credentials, tmp_path):
        """Test refreshing expired token."""
        mock_credentials.valid = False
        mock_credentials.expired = True

        token_path = tmp_path / "token.json"
        token_path.write_text('{"token": "expired"}')

        with patch("src.google_drive.auth.TOKEN_PATH", token_path), \
             patch("src.google_drive.auth.CONFIG_DIR", tmp_path), \
             patch("src.google_drive.auth.Credentials") as MockCreds, \
             patch("src.google_drive.auth.Request") as MockRequest:
            MockCreds.from_authorized_user_file.return_value = mock_credentials

            from src.google_drive.auth import get_credentials
            creds = get_credentials()

            mock_credentials.refresh.assert_called_once()
            assert creds == mock_credentials

    def test_runs_oauth_flow_when_no_token(self, sample_client_config, tmp_path):
        """Test running OAuth flow when no token exists."""
        token_path = tmp_path / "token.json"
        config_dir = tmp_path

        mock_flow = MagicMock()
        mock_new_creds = MagicMock()
        mock_new_creds.to_json.return_value = '{"token": "new"}'
        mock_flow.run_local_server.return_value = mock_new_creds

        with patch("src.google_drive.auth.TOKEN_PATH", token_path), \
             patch("src.google_drive.auth.CONFIG_DIR", config_dir), \
             patch("src.google_drive.auth._load_client_config", return_value=sample_client_config), \
             patch("src.google_drive.auth.InstalledAppFlow") as MockFlow:
            MockFlow.from_client_config.return_value = mock_flow

            from src.google_drive.auth import get_credentials
            creds = get_credentials()

            MockFlow.from_client_config.assert_called_once()
            mock_flow.run_local_server.assert_called_once()
            assert creds == mock_new_creds
            assert token_path.exists()

    def test_saves_token_after_auth(self, sample_client_config, tmp_path):
        """Test that token is saved after authentication."""
        token_path = tmp_path / "token.json"
        config_dir = tmp_path

        mock_flow = MagicMock()
        mock_new_creds = MagicMock()
        mock_new_creds.to_json.return_value = '{"token": "new_token"}'
        mock_flow.run_local_server.return_value = mock_new_creds

        with patch("src.google_drive.auth.TOKEN_PATH", token_path), \
             patch("src.google_drive.auth.CONFIG_DIR", config_dir), \
             patch("src.google_drive.auth._load_client_config", return_value=sample_client_config), \
             patch("src.google_drive.auth.InstalledAppFlow") as MockFlow:
            MockFlow.from_client_config.return_value = mock_flow

            from src.google_drive.auth import get_credentials
            get_credentials()

            saved_token = json.loads(token_path.read_text())
            assert saved_token == {"token": "new_token"}


class TestLoadClientConfig:
    """Tests for _load_client_config function."""

    @pytest.fixture
    def sample_config_json(self):
        """Sample config as JSON string."""
        return json.dumps({
            "installed": {
                "client_id": "env_client_id",
                "client_secret": "env_secret",
            }
        })

    def test_loads_from_env_var(self, sample_config_json, tmp_path):
        """Test loading config from environment variable."""
        with patch.dict(os.environ, {"GOOGLE_DRIVE_OAUTH_CREDENTIALS": sample_config_json}), \
             patch("src.google_drive.auth.CREDENTIALS_PATH", tmp_path / "creds.json"):
            from src.google_drive.auth import _load_client_config
            config = _load_client_config()

            assert config["installed"]["client_id"] == "env_client_id"

    def test_loads_from_config_dir(self, tmp_path):
        """Test loading config from config directory."""
        creds_path = tmp_path / "credentials.json"
        creds_path.write_text(json.dumps({
            "installed": {"client_id": "file_client_id"}
        }))

        with patch.dict(os.environ, {}, clear=True), \
             patch("src.google_drive.auth.CREDENTIALS_PATH", creds_path):
            from src.google_drive.auth import _load_client_config
            config = _load_client_config()
            assert config["installed"]["client_id"] == "file_client_id"

    def test_loads_from_project_root(self, tmp_path, monkeypatch):
        """Test loading config from project root."""
        monkeypatch.chdir(tmp_path)
        creds_path = tmp_path / "credentials.json"
        creds_path.write_text(json.dumps({
            "installed": {"client_id": "project_client_id"}
        }))

        with patch.dict(os.environ, {}, clear=True), \
             patch("src.google_drive.auth.CREDENTIALS_PATH", tmp_path / "nonexistent.json"), \
             patch("src.google_drive.auth.MCP_CREDENTIAL_PATHS", []):
            from src.google_drive.auth import _load_client_config
            config = _load_client_config()
            assert config["installed"]["client_id"] == "project_client_id"

    def test_loads_from_supported_mcp_path(self, tmp_path, monkeypatch):
        """Test loading config from a supported MCP config path."""
        fake_mcp_path = tmp_path / "gcp-oauth.keys.json"
        fake_mcp_path.write_text(json.dumps({
            "installed": {"client_id": "mcp_client_id"}
        }))

        monkeypatch.chdir(tmp_path)

        with patch.dict(os.environ, {}, clear=True), \
             patch("src.google_drive.auth.CREDENTIALS_PATH", tmp_path / "nonexistent.json"), \
             patch("src.google_drive.auth.MCP_CREDENTIAL_PATHS", [fake_mcp_path]):
            from src.google_drive.auth import _load_client_config
            config = _load_client_config()
            assert config["installed"]["client_id"] == "mcp_client_id"

    def test_raises_when_no_config_found(self, tmp_path, monkeypatch):
        """Test raising error when no config is found."""
        monkeypatch.chdir(tmp_path)

        with patch.dict(os.environ, {}, clear=True), \
             patch("src.google_drive.auth.CREDENTIALS_PATH", tmp_path / "nonexistent.json"), \
             patch("src.google_drive.auth.MCP_CREDENTIAL_PATHS", []):
            from src.google_drive.auth import _load_client_config
            with pytest.raises(FileNotFoundError, match="credentials not found"):
                _load_client_config()
