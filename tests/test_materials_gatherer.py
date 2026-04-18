"""Tests for MaterialsGathererAgent."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.materials_gatherer import MaterialsGathererAgent
from src.models import ConfigOutput, MaterialsOutput, DocumentContent


class TestMaterialsGathererAgent:
    """Tests for MaterialsGathererAgent."""

    @pytest.fixture
    def mock_drive_client(self):
        """Create a mock Google Drive client."""
        client = MagicMock()
        client.list_folder = AsyncMock()
        client.read_google_doc = AsyncMock()
        client.download_file_content = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_gather_google_docs(self, mock_drive_client, sample_config):
        """Test gathering Google Docs from folders."""
        # Setup mock
        mock_drive_client.list_folder.return_value = [
            {
                "id": "doc_1",
                "name": "Resume.docx",
                "mimeType": "application/vnd.google-apps.document",
            }
        ]
        mock_drive_client.read_google_doc.return_value = "# Resume\n\nContent here..."

        agent = MaterialsGathererAgent(google_drive_client=mock_drive_client)
        result = await agent.run(sample_config)

        assert isinstance(result, MaterialsOutput)
        assert result.total_documents == 2  # 2 folders, 1 doc each
        assert len(result.extraction_errors) == 0

        # Verify list_folder was called for each folder
        assert mock_drive_client.list_folder.call_count == 2

    @pytest.mark.asyncio
    async def test_gather_mixed_file_types(self, mock_drive_client, sample_config):
        """Test gathering different file types."""
        mock_drive_client.list_folder.return_value = [
            {
                "id": "doc_1",
                "name": "Resume.docx",
                "mimeType": "application/vnd.google-apps.document",
            },
            {
                "id": "pdf_1",
                "name": "Certificate.pdf",
                "mimeType": "application/pdf",
            },
            {
                "id": "txt_1",
                "name": "Notes.txt",
                "mimeType": "text/plain",
            },
        ]
        mock_drive_client.read_google_doc.return_value = "Doc content"
        mock_drive_client.download_file_content.return_value = "Downloaded content"

        agent = MaterialsGathererAgent(google_drive_client=mock_drive_client)

        # Only use first folder for this test
        config = ConfigOutput(source_folders=["folder_1"])
        result = await agent.run(config)

        assert result.total_documents == 3
        # Verify different read methods were called
        mock_drive_client.read_google_doc.assert_called()

    @pytest.mark.asyncio
    async def test_skip_unsupported_file_types(self, mock_drive_client, sample_config):
        """Test that unsupported file types are skipped."""
        mock_drive_client.list_folder.return_value = [
            {
                "id": "img_1",
                "name": "photo.jpg",
                "mimeType": "image/jpeg",
            },
            {
                "id": "doc_1",
                "name": "Resume.docx",
                "mimeType": "application/vnd.google-apps.document",
            },
        ]
        mock_drive_client.read_google_doc.return_value = "Doc content"

        agent = MaterialsGathererAgent(google_drive_client=mock_drive_client)
        config = ConfigOutput(source_folders=["folder_1"])
        result = await agent.run(config)

        # Only the doc should be included
        assert result.total_documents == 1

    @pytest.mark.asyncio
    async def test_handle_folder_error_gracefully(self, mock_drive_client, sample_config):
        """Test that folder errors don't stop the entire process."""
        mock_drive_client.list_folder.side_effect = [
            Exception("API Error"),
            [{"id": "doc_1", "name": "Resume.docx", "mimeType": "application/vnd.google-apps.document"}],
        ]
        mock_drive_client.read_google_doc.return_value = "Content"

        agent = MaterialsGathererAgent(google_drive_client=mock_drive_client)
        result = await agent.run(sample_config)

        # Should still get docs from second folder
        assert result.total_documents == 1
        # Should have one error recorded
        assert len(result.extraction_errors) == 1
        assert "API Error" in result.extraction_errors[0]

    @pytest.mark.asyncio
    async def test_handle_file_read_error_gracefully(self, mock_drive_client, sample_config):
        """Test that file read errors don't stop the entire process."""
        mock_drive_client.list_folder.return_value = [
            {"id": "doc_1", "name": "Resume.docx", "mimeType": "application/vnd.google-apps.document"},
            {"id": "doc_2", "name": "Projects.docx", "mimeType": "application/vnd.google-apps.document"},
        ]
        mock_drive_client.read_google_doc.side_effect = [
            Exception("Read Error"),
            "Content for doc 2",
        ]

        agent = MaterialsGathererAgent(google_drive_client=mock_drive_client)
        config = ConfigOutput(source_folders=["folder_1"])
        result = await agent.run(config)

        # Should still get the second doc
        assert result.total_documents == 1

    @pytest.mark.asyncio
    async def test_empty_folder_returns_empty_result(self, mock_drive_client, sample_config):
        """Test that empty folders result in empty documents list."""
        mock_drive_client.list_folder.return_value = []

        agent = MaterialsGathererAgent(google_drive_client=mock_drive_client)
        config = ConfigOutput(source_folders=["folder_1"])
        result = await agent.run(config)

        assert result.total_documents == 0
        assert len(result.documents) == 0
        assert len(result.extraction_errors) == 0

    @pytest.mark.asyncio
    async def test_document_content_structure(self, mock_drive_client, sample_config):
        """Test that document content has correct structure."""
        mock_drive_client.list_folder.return_value = [
            {
                "id": "doc_1",
                "name": "Resume.docx",
                "mimeType": "application/vnd.google-apps.document",
            }
        ]
        mock_drive_client.read_google_doc.return_value = "# Resume Content"

        agent = MaterialsGathererAgent(google_drive_client=mock_drive_client)
        config = ConfigOutput(source_folders=["folder_1"])
        result = await agent.run(config)

        doc = result.documents[0]
        assert isinstance(doc, DocumentContent)
        assert doc.source_folder == "folder_1"
        assert doc.file_name == "Resume.docx"
        assert doc.file_type == "google_doc"
        assert doc.content == "# Resume Content"
        assert "id" in doc.metadata
