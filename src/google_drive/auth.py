"""Google Drive OAuth authentication."""

import json
import os
from pathlib import Path

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/documents",
]

CONFIG_DIR = Path.home() / ".cv-builder"
TOKEN_PATH = CONFIG_DIR / "token.json"
CREDENTIALS_PATH = CONFIG_DIR / "credentials.json"
MCP_CREDENTIAL_PATHS = [
    Path.home() / ".config" / "google-drive-mcp" / "gcp-oauth.keys.json",
    Path.home() / ".config" / "gcp-oauth.keys.json",
]


def get_credentials() -> Credentials:
    """Get valid Google credentials, prompting for auth if needed.

    Returns:
        Valid Google OAuth credentials.
    """
    creds = None

    # Load existing token
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    # Refresh or get new credentials
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            creds = _run_oauth_flow()

        # Save token
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        TOKEN_PATH.write_text(creds.to_json())

    return creds


def _run_oauth_flow() -> Credentials:
    """Run OAuth flow to get new credentials.

    Returns:
        New credentials from OAuth flow.
    """
    client_config = _load_client_config()

    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    creds = flow.run_local_server(port=0)

    return creds


def _load_client_config() -> dict:
    """Load OAuth client configuration.

    Returns:
        OAuth client configuration dict.

    Raises:
        FileNotFoundError: If no credentials configuration is found.
    """
    # Priority 1: Environment variable
    env_creds = os.environ.get("GOOGLE_DRIVE_OAUTH_CREDENTIALS")
    if env_creds:
        return json.loads(env_creds)

    # Priority 2: Config dir
    if CREDENTIALS_PATH.exists():
        return json.loads(CREDENTIALS_PATH.read_text())

    # Priority 3: Known MCP/connector config locations
    for path in MCP_CREDENTIAL_PATHS:
        if path.exists():
            return json.loads(path.read_text())

    # Priority 4: Project root
    local_path = Path("credentials.json")
    if local_path.exists():
        return json.loads(local_path.read_text())

    raise FileNotFoundError(
        "Google OAuth credentials not found. Set GOOGLE_DRIVE_OAUTH_CREDENTIALS "
        "env var or place credentials.json in ~/.cv-builder/, a supported "
        "MCP config path, or the project root."
    )
