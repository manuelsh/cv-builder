"""Google Drive client using direct API."""

from typing import Any

from src.google_drive.auth import get_credentials
from src.google_drive import api


class GoogleDriveClient:
    """Client for Google Drive operations via direct API."""

    def __init__(self):
        """Initialize the client."""
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
        """List contents of a Google Drive folder.

        Args:
            folder_id: The folder ID.

        Returns:
            List of file metadata dicts.
        """
        self._ensure_services()
        return api.list_files_in_folder(self._drive_service, folder_id)

    async def read_google_doc(
        self,
        document_id: str,
        format: str = "markdown",
    ) -> str:
        """Read content of a Google Doc.

        Args:
            document_id: The document ID.
            format: Output format (text, markdown, html).

        Returns:
            Document content as string.
        """
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
        """Download and return file content as text.

        Args:
            file_id: The file ID.

        Returns:
            File content as string.
        """
        self._ensure_services()
        return api.download_file(self._drive_service, file_id)

    async def create_google_doc(
        self,
        name: str,
        content: str,
        parent_folder_id: str | None = None,
    ) -> dict[str, str]:
        """Create a new Google Doc.

        Args:
            name: Document name.
            content: Initial content.
            parent_folder_id: Optional parent folder ID.

        Returns:
            Dict with 'id' and 'url' of created document.
        """
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
        """Apply paragraph formatting to a Google Doc.

        Args:
            document_id: The document ID.
            text_to_find: Text to find for formatting.
            named_style_type: Style type (TITLE, HEADING_1, etc.).
            alignment: Text alignment (START, CENTER, END).
            match_instance: Which instance to format (default: 1).

        Returns:
            True if successful, False if text not found.
        """
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
        """Apply text formatting to a Google Doc.

        Args:
            document_id: The document ID.
            text_to_find: Text to find for formatting.
            bold: Make text bold.
            italic: Make text italic.
            match_instance: Which instance to format (default: 1).

        Returns:
            True if successful, False if text not found.
        """
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
        """Get document content with optional formatting info.

        Args:
            document_id: The document ID.
            include_formatting: Include formatting markers.

        Returns:
            Document content.
        """
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
        """Find the start and end index of text in document.

        Args:
            doc: Document structure dict.
            text: Text to find.
            instance: Which instance to find (1-indexed).

        Returns:
            Tuple of (start_index, end_index) or (None, None) if not found.
        """
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
        """Extract content with formatting markers.

        Args:
            doc: Document structure dict.

        Returns:
            Content with markdown-style formatting markers.
        """
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
