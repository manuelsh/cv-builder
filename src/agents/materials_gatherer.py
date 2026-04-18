"""MaterialsGathererAgent - fetches user materials from Google Drive."""

from typing import Any

from src.agents.base import BaseAgent
from src.google_drive.client import GoogleDriveClient
from src.models import ConfigOutput, MaterialsOutput, DocumentContent


class MaterialsGathererAgent(BaseAgent):
    """Agent that fetches user materials from Google Drive folders."""

    agent_name = "materials_gatherer"

    def __init__(
        self,
        google_drive_client: GoogleDriveClient | None = None,
        **kwargs: Any,
    ):
        """Initialize the agent.

        Args:
            google_drive_client: Google Drive client. Creates one if not provided.
            **kwargs: Additional arguments for BaseAgent.
        """
        super().__init__(**kwargs)
        self.drive = google_drive_client or GoogleDriveClient()

    async def run(self, config: ConfigOutput) -> MaterialsOutput:
        """Fetch all materials from Google Drive folders.

        Args:
            config: Configuration with source folder IDs.

        Returns:
            MaterialsOutput with all extracted documents.
        """
        documents: list[DocumentContent] = []
        errors: list[str] = []

        for folder_id in config.source_folders:
            try:
                folder_docs = await self._process_folder(folder_id)
                documents.extend(folder_docs)
            except Exception as e:
                error_msg = f"Error processing folder {folder_id}: {e}"
                errors.append(error_msg)
                print(f"Warning: {error_msg}")

        return MaterialsOutput(
            documents=documents,
            total_documents=len(documents),
            extraction_errors=errors,
        )

    async def _process_folder(self, folder_id: str) -> list[DocumentContent]:
        """Process a single folder.

        Args:
            folder_id: Google Drive folder ID.

        Returns:
            List of extracted documents.
        """
        files = await self.drive.list_folder(folder_id)
        documents: list[DocumentContent] = []

        for file in files:
            try:
                doc = await self._read_file(file, folder_id)
                if doc:
                    documents.append(doc)
            except Exception as e:
                print(f"Warning: Could not read {file.get('name', 'unknown')}: {e}")

        return documents

    async def _read_file(
        self,
        file: dict[str, Any],
        folder_id: str,
    ) -> DocumentContent | None:
        """Read a single file based on its type.

        Args:
            file: File metadata dict.
            folder_id: Source folder ID.

        Returns:
            DocumentContent or None if unsupported type.
        """
        file_id = file["id"]
        file_name = file["name"]
        mime_type = file.get("mimeType", "")

        # Determine how to read based on type
        if "document" in mime_type:
            content = await self.drive.read_google_doc(file_id, format="markdown")
            file_type = "google_doc"
        elif file_name.endswith(".pdf"):
            # For PDFs, try to download content
            # Note: In production, we might want to convert to Google Doc first
            content = await self.drive.download_file_content(file_id)
            file_type = "pdf"
        elif file_name.endswith((".txt", ".md")):
            content = await self.drive.download_file_content(file_id)
            file_type = "text"
        else:
            # Skip unsupported file types
            return None

        if not content:
            return None

        return DocumentContent(
            source_folder=folder_id,
            file_name=file_name,
            file_type=file_type,
            content=content,
            metadata={"id": file_id, "mimeType": mime_type},
        )
