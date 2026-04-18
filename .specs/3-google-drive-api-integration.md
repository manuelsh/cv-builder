# Google Drive API Direct Integration

## Overview

Replace the MCP-based Google Drive client with a direct Google Drive API implementation using `google-api-python-client`. This makes the CLI fully standalone without requiring Claude Code or MCP servers.

## Current State

- `src/google_drive/client.py` has `GoogleDriveClient` class expecting an `mcp_caller`
- Without `mcp_caller`, all methods return empty/mock results
- CLI runs but can't actually access Google Drive

## Goals

1. Use Google Drive API directly via `google-api-python-client`
2. Implement OAuth2 flow with local token storage
3. Keep the same interface so existing agents work unchanged
4. Remove MCP dependency entirely

## Dependencies to Add

```toml
# pyproject.toml
dependencies = [
    # ... existing ...
    "google-api-python-client>=2.100.0",
    "google-auth-oauthlib>=1.1.0",
    "google-auth-httplib2>=0.1.1",
]
```

## Required Google API Scopes

```python
SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",      # List folders, read files
    "https://www.googleapis.com/auth/drive.file",          # Create files in app-created folders
    "https://www.googleapis.com/auth/documents",           # Read/write Google Docs
]
```

## OAuth Configuration

### Credentials Source (Priority Order)

1. `GOOGLE_DRIVE_OAUTH_CREDENTIALS` env var (JSON string) - same as MCP uses
2. `~/.cv-builder/credentials.json` file
3. `./credentials.json` in project root

### Token Storage

- Store tokens at `~/.cv-builder/token.json`
- Auto-refresh expired tokens
- Prompt for re-auth if refresh fails

## Implementation

### File Structure

```
src/google_drive/
├── __init__.py
├── client.py          # Main client (update existing)
├── auth.py            # OAuth flow and token management (new)
└── api.py             # Low-level API wrappers (new)
```

### auth.py - OAuth Handler

```python
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


def get_credentials() -> Credentials:
    """Get valid Google credentials, prompting for auth if needed."""
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
    """Run OAuth flow to get new credentials."""
    client_config = _load_client_config()

    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    creds = flow.run_local_server(port=0)

    return creds


def _load_client_config() -> dict:
    """Load OAuth client configuration."""
    # Priority 1: Environment variable
    env_creds = os.environ.get("GOOGLE_DRIVE_OAUTH_CREDENTIALS")
    if env_creds:
        return json.loads(env_creds)

    # Priority 2: Config dir
    if CREDENTIALS_PATH.exists():
        return json.loads(CREDENTIALS_PATH.read_text())

    # Priority 3: Project root
    local_path = Path("credentials.json")
    if local_path.exists():
        return json.loads(local_path.read_text())

    raise FileNotFoundError(
        "Google OAuth credentials not found. Set GOOGLE_DRIVE_OAUTH_CREDENTIALS "
        "env var or place credentials.json in ~/.cv-builder/ or project root."
    )
```

### api.py - API Wrappers

```python
"""Low-level Google Drive and Docs API wrappers."""

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials


def get_drive_service(creds: Credentials):
    """Build Google Drive API service."""
    return build("drive", "v3", credentials=creds)


def get_docs_service(creds: Credentials):
    """Build Google Docs API service."""
    return build("docs", "v1", credentials=creds)


def list_files_in_folder(service, folder_id: str) -> list[dict]:
    """List files in a Google Drive folder."""
    query = f"'{folder_id}' in parents and trashed = false"
    results = service.files().list(
        q=query,
        fields="files(id, name, mimeType)",
        pageSize=100,
    ).execute()
    return results.get("files", [])


def export_google_doc(service, doc_id: str, mime_type: str = "text/plain") -> str:
    """Export Google Doc content."""
    # For Google Docs, use export
    content = service.files().export(
        fileId=doc_id,
        mimeType=mime_type,
    ).execute()
    return content.decode("utf-8") if isinstance(content, bytes) else content


def download_file(service, file_id: str) -> str:
    """Download file content."""
    content = service.files().get_media(fileId=file_id).execute()
    return content.decode("utf-8") if isinstance(content, bytes) else content


def create_google_doc(docs_service, drive_service, name: str, content: str, parent_id: str | None) -> dict:
    """Create a new Google Doc with content."""
    # Create empty doc
    doc = docs_service.documents().create(body={"title": name}).execute()
    doc_id = doc["documentId"]

    # Move to folder if specified
    if parent_id:
        drive_service.files().update(
            fileId=doc_id,
            addParents=parent_id,
            fields="id, parents",
        ).execute()

    # Insert content
    if content:
        docs_service.documents().batchUpdate(
            documentId=doc_id,
            body={
                "requests": [{
                    "insertText": {
                        "location": {"index": 1},
                        "text": content,
                    }
                }]
            },
        ).execute()

    return {
        "id": doc_id,
        "url": f"https://docs.google.com/document/d/{doc_id}/edit",
    }


def format_paragraph(docs_service, doc_id: str, start_index: int, end_index: int, style: dict) -> None:
    """Apply paragraph formatting."""
    docs_service.documents().batchUpdate(
        documentId=doc_id,
        body={
            "requests": [{
                "updateParagraphStyle": {
                    "range": {"startIndex": start_index, "endIndex": end_index},
                    "paragraphStyle": style,
                    "fields": ",".join(style.keys()),
                }
            }]
        },
    ).execute()


def format_text(docs_service, doc_id: str, start_index: int, end_index: int, style: dict) -> None:
    """Apply text formatting."""
    docs_service.documents().batchUpdate(
        documentId=doc_id,
        body={
            "requests": [{
                "updateTextStyle": {
                    "range": {"startIndex": start_index, "endIndex": end_index},
                    "textStyle": style,
                    "fields": ",".join(style.keys()),
                }
            }]
        },
    ).execute()


def get_document(docs_service, doc_id: str) -> dict:
    """Get full document structure."""
    return docs_service.documents().get(documentId=doc_id).execute()
```

### client.py - Updated Client

```python
"""Google Drive client using direct API."""

from typing import Any

from src.google_drive.auth import get_credentials
from src.google_drive import api


class GoogleDriveClient:
    """Client for Google Drive operations via direct API."""

    def __init__(self):
        """Initialize the client with Google API credentials."""
        self._creds = None
        self._drive_service = None
        self._docs_service = None

    def _ensure_services(self):
        """Lazily initialize API services."""
        if self._drive_service is None:
            self._creds = get_credentials()
            self._drive_service = api.get_drive_service(self._creds)
            self._docs_service = api.get_docs_service(self._creds)

    async def list_folder(self, folder_id: str) -> list[dict[str, Any]]:
        """List contents of a Google Drive folder."""
        self._ensure_services()
        return api.list_files_in_folder(self._drive_service, folder_id)

    async def read_google_doc(self, document_id: str, format: str = "markdown") -> str:
        """Read content of a Google Doc."""
        self._ensure_services()

        # Map format to MIME type
        mime_map = {
            "text": "text/plain",
            "markdown": "text/plain",  # Google doesn't support markdown export
            "html": "text/html",
        }
        mime_type = mime_map.get(format, "text/plain")

        return api.export_google_doc(self._drive_service, document_id, mime_type)

    async def download_file_content(self, file_id: str) -> str:
        """Download and return file content as text."""
        self._ensure_services()
        return api.download_file(self._drive_service, file_id)

    async def create_google_doc(
        self,
        name: str,
        content: str,
        parent_folder_id: str | None = None,
    ) -> dict[str, str]:
        """Create a new Google Doc."""
        self._ensure_services()
        return api.create_google_doc(
            self._docs_service,
            self._drive_service,
            name,
            content,
            parent_folder_id,
        )

    async def format_paragraph(
        self,
        document_id: str,
        text_to_find: str | None = None,
        named_style_type: str | None = None,
        alignment: str | None = None,
        match_instance: int = 1,
    ) -> bool:
        """Apply paragraph formatting to a Google Doc."""
        self._ensure_services()

        if not text_to_find:
            return True

        # Get document to find text position
        doc = api.get_document(self._docs_service, document_id)
        start, end = self._find_text_range(doc, text_to_find, match_instance)

        if start is None:
            return False

        style = {}
        if named_style_type:
            style["namedStyleType"] = named_style_type
        if alignment:
            style["alignment"] = alignment

        if style:
            api.format_paragraph(self._docs_service, document_id, start, end, style)

        return True

    async def format_text(
        self,
        document_id: str,
        text_to_find: str | None = None,
        bold: bool | None = None,
        italic: bool | None = None,
        match_instance: int = 1,
    ) -> bool:
        """Apply text formatting to a Google Doc."""
        self._ensure_services()

        if not text_to_find:
            return True

        doc = api.get_document(self._docs_service, document_id)
        start, end = self._find_text_range(doc, text_to_find, match_instance)

        if start is None:
            return False

        style = {}
        if bold is not None:
            style["bold"] = bold
        if italic is not None:
            style["italic"] = italic

        if style:
            api.format_text(self._docs_service, document_id, start, end, style)

        return True

    async def get_doc_content(
        self,
        document_id: str,
        include_formatting: bool = False,
    ) -> str:
        """Get document content."""
        self._ensure_services()

        if include_formatting:
            doc = api.get_document(self._docs_service, document_id)
            return self._extract_formatted_content(doc)

        return api.export_google_doc(self._drive_service, document_id, "text/plain")

    def _find_text_range(
        self,
        doc: dict,
        text: str,
        instance: int = 1,
    ) -> tuple[int | None, int | None]:
        """Find the start and end index of text in document."""
        content = doc.get("body", {}).get("content", [])
        full_text = ""

        for element in content:
            if "paragraph" in element:
                for elem in element["paragraph"].get("elements", []):
                    if "textRun" in elem:
                        full_text += elem["textRun"].get("content", "")

        # Find nth instance
        start = -1
        for _ in range(instance):
            start = full_text.find(text, start + 1)
            if start == -1:
                return None, None

        # Adjust for document structure (index 1 is start of body)
        return start + 1, start + len(text) + 1

    def _extract_formatted_content(self, doc: dict) -> str:
        """Extract content with formatting markers."""
        content = doc.get("body", {}).get("content", [])
        result = []

        for element in content:
            if "paragraph" in element:
                para = element["paragraph"]
                style = para.get("paragraphStyle", {}).get("namedStyleType", "NORMAL_TEXT")

                text_parts = []
                for elem in para.get("elements", []):
                    if "textRun" in elem:
                        text = elem["textRun"].get("content", "")
                        text_style = elem["textRun"].get("textStyle", {})

                        if text_style.get("bold"):
                            text = f"**{text.strip()}**"
                        if text_style.get("italic"):
                            text = f"_{text.strip()}_"

                        text_parts.append(text)

                line = "".join(text_parts)
                if style == "TITLE":
                    line = f"# {line}"
                elif style == "HEADING_1":
                    line = f"## {line}"
                elif style == "HEADING_2":
                    line = f"### {line}"

                result.append(line)

        return "".join(result)
```

## CLI Auth Command

Add a new CLI command to handle authentication:

```python
# In cli.py, add auth subcommand

def main():
    # ... existing subparsers ...

    auth_parser = subparsers.add_parser(
        "auth",
        help="Authenticate with Google Drive",
    )
    auth_parser.add_argument(
        "--status",
        action="store_true",
        help="Check authentication status",
    )


def run_auth(args) -> int:
    """Run the auth command."""
    from src.google_drive.auth import get_credentials, TOKEN_PATH

    if args.status:
        if TOKEN_PATH.exists():
            print(f"Authenticated. Token stored at: {TOKEN_PATH}")
            return 0
        else:
            print("Not authenticated. Run 'cv-builder auth' to authenticate.")
            return 1

    try:
        get_credentials()
        print("Authentication successful!")
        return 0
    except Exception as e:
        print(f"Authentication failed: {e}")
        return 1
```

## Migration Steps

1. Add new dependencies to `pyproject.toml`
2. Create `src/google_drive/auth.py`
3. Create `src/google_drive/api.py`
4. Update `src/google_drive/client.py` (remove mcp_caller)
5. Update `src/google_drive/__init__.py` exports
6. Add `auth` subcommand to CLI
7. Update tests to mock the Google API instead of mcp_caller
8. Update README with new auth instructions

## Testing Strategy

### Unit Tests (Mock API)

```python
# tests/test_google_drive_client.py

@pytest.fixture
def mock_drive_service():
    service = MagicMock()
    service.files().list().execute.return_value = {
        "files": [
            {"id": "doc1", "name": "Resume.gdoc", "mimeType": "application/vnd.google-apps.document"},
        ]
    }
    return service

@pytest.fixture
def mock_docs_service():
    service = MagicMock()
    service.documents().get().execute.return_value = {
        "body": {"content": [{"paragraph": {"elements": [{"textRun": {"content": "Test"}}]}}]}
    }
    return service
```

### Integration Tests (Optional, requires real credentials)

```python
@pytest.mark.integration
async def test_real_folder_listing():
    client = GoogleDriveClient()
    files = await client.list_folder("known_test_folder_id")
    assert len(files) > 0
```

## README Updates

```markdown
## Authentication

Before using CV Builder, authenticate with Google Drive:

```bash
cv-builder auth
```

This opens a browser for Google OAuth. Tokens are stored at `~/.cv-builder/token.json`.

### Credentials Setup

Option 1: Use environment variable (recommended for CI):
```bash
export GOOGLE_DRIVE_OAUTH_CREDENTIALS='{"installed":{"client_id":"..."}}'
```

Option 2: Place `credentials.json` in `~/.cv-builder/` or project root.

To create credentials:
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project and enable Drive API and Docs API
3. Create OAuth 2.0 credentials (Desktop app)
4. Download as `credentials.json`
```
