"""Tests for GoogleDriveClient with direct API."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models import ConfigOutput


class TestGoogleDriveClient:
    """Tests for GoogleDriveClient."""

    @pytest.fixture
    def mock_services(self):
        """Create mock Google services."""
        drive_service = MagicMock()
        docs_service = MagicMock()
        return drive_service, docs_service

    @pytest.fixture
    def mock_credentials(self):
        """Create mock credentials."""
        creds = MagicMock()
        creds.valid = True
        return creds

    @pytest.mark.asyncio
    async def test_list_folder(self, mock_services, mock_credentials):
        """Test listing folder contents."""
        drive_service, docs_service = mock_services

        with patch("src.google_drive.client.get_credentials", return_value=mock_credentials), \
             patch("src.google_drive.client.api") as mock_api:
            mock_api.get_drive_service.return_value = drive_service
            mock_api.get_docs_service.return_value = docs_service
            mock_api.list_files_in_folder.return_value = [
                {"id": "doc1", "name": "Resume.gdoc", "mimeType": "application/vnd.google-apps.document"},
            ]

            from src.google_drive.client import GoogleDriveClient
            client = GoogleDriveClient()
            files = await client.list_folder("folder_123")

            assert len(files) == 1
            assert files[0]["name"] == "Resume.gdoc"
            mock_api.list_files_in_folder.assert_called_once_with(drive_service, "folder_123")

    @pytest.mark.asyncio
    async def test_read_google_doc(self, mock_services, mock_credentials):
        """Test reading Google Doc content."""
        drive_service, docs_service = mock_services

        with patch("src.google_drive.client.get_credentials", return_value=mock_credentials), \
             patch("src.google_drive.client.api") as mock_api:
            mock_api.get_drive_service.return_value = drive_service
            mock_api.get_docs_service.return_value = docs_service
            mock_api.export_google_doc.return_value = "Document content"

            from src.google_drive.client import GoogleDriveClient
            client = GoogleDriveClient()
            content = await client.read_google_doc("doc_123")

            assert content == "Document content"
            mock_api.export_google_doc.assert_called_once()

    @pytest.mark.asyncio
    async def test_read_google_doc_format_mapping(self, mock_services, mock_credentials):
        """Test format parameter mapping."""
        drive_service, docs_service = mock_services

        with patch("src.google_drive.client.get_credentials", return_value=mock_credentials), \
             patch("src.google_drive.client.api") as mock_api:
            mock_api.get_drive_service.return_value = drive_service
            mock_api.get_docs_service.return_value = docs_service
            mock_api.export_google_doc.return_value = "Content"

            from src.google_drive.client import GoogleDriveClient
            client = GoogleDriveClient()

            # Test text format
            await client.read_google_doc("doc_123", format="text")
            call_args = mock_api.export_google_doc.call_args
            assert call_args[0][2] == "text/plain"

            # Test html format
            await client.read_google_doc("doc_123", format="html")
            call_args = mock_api.export_google_doc.call_args
            assert call_args[0][2] == "text/html"

    @pytest.mark.asyncio
    async def test_download_file_content(self, mock_services, mock_credentials):
        """Test downloading file content."""
        drive_service, docs_service = mock_services

        with patch("src.google_drive.client.get_credentials", return_value=mock_credentials), \
             patch("src.google_drive.client.api") as mock_api:
            mock_api.get_drive_service.return_value = drive_service
            mock_api.get_docs_service.return_value = docs_service
            mock_api.download_file.return_value = "File content"

            from src.google_drive.client import GoogleDriveClient
            client = GoogleDriveClient()
            content = await client.download_file_content("file_123")

            assert content == "File content"

    @pytest.mark.asyncio
    async def test_create_google_doc(self, mock_services, mock_credentials):
        """Test creating a Google Doc."""
        drive_service, docs_service = mock_services

        with patch("src.google_drive.client.get_credentials", return_value=mock_credentials), \
             patch("src.google_drive.client.api") as mock_api:
            mock_api.get_drive_service.return_value = drive_service
            mock_api.get_docs_service.return_value = docs_service
            mock_api.create_google_doc.return_value = {
                "id": "new_doc_123",
                "url": "https://docs.google.com/document/d/new_doc_123/edit",
            }

            from src.google_drive.client import GoogleDriveClient
            client = GoogleDriveClient()
            result = await client.create_google_doc("Test Doc", "Content", "parent_folder")

            assert result["id"] == "new_doc_123"
            assert "docs.google.com" in result["url"]
            mock_api.create_google_doc.assert_called_once_with(
                docs_service,
                drive_service,
                "Test Doc",
                "Content",
                "parent_folder",
            )

    @pytest.mark.asyncio
    async def test_format_paragraph(self, mock_services, mock_credentials):
        """Test applying paragraph formatting."""
        drive_service, docs_service = mock_services

        with patch("src.google_drive.client.get_credentials", return_value=mock_credentials), \
             patch("src.google_drive.client.api") as mock_api:
            mock_api.get_drive_service.return_value = drive_service
            mock_api.get_docs_service.return_value = docs_service
            mock_api.get_document.return_value = {
                "body": {
                    "content": [
                        {
                            "paragraph": {
                                "elements": [
                                    {"textRun": {"content": "Hello World"}}
                                ]
                            }
                        }
                    ]
                }
            }

            from src.google_drive.client import GoogleDriveClient
            client = GoogleDriveClient()
            result = await client.format_paragraph(
                "doc_123",
                text_to_find="Hello",
                named_style_type="HEADING_1",
            )

            assert result is True
            mock_api.format_paragraph.assert_called_once()

    @pytest.mark.asyncio
    async def test_format_paragraph_text_not_found(self, mock_services, mock_credentials):
        """Test formatting when text is not found."""
        drive_service, docs_service = mock_services

        with patch("src.google_drive.client.get_credentials", return_value=mock_credentials), \
             patch("src.google_drive.client.api") as mock_api:
            mock_api.get_drive_service.return_value = drive_service
            mock_api.get_docs_service.return_value = docs_service
            mock_api.get_document.return_value = {
                "body": {
                    "content": [
                        {
                            "paragraph": {
                                "elements": [
                                    {"textRun": {"content": "Different text"}}
                                ]
                            }
                        }
                    ]
                }
            }

            from src.google_drive.client import GoogleDriveClient
            client = GoogleDriveClient()
            result = await client.format_paragraph(
                "doc_123",
                text_to_find="NotFound",
                named_style_type="HEADING_1",
            )

            assert result is False
            mock_api.format_paragraph.assert_not_called()

    @pytest.mark.asyncio
    async def test_format_text(self, mock_services, mock_credentials):
        """Test applying text formatting."""
        drive_service, docs_service = mock_services

        with patch("src.google_drive.client.get_credentials", return_value=mock_credentials), \
             patch("src.google_drive.client.api") as mock_api:
            mock_api.get_drive_service.return_value = drive_service
            mock_api.get_docs_service.return_value = docs_service
            mock_api.get_document.return_value = {
                "body": {
                    "content": [
                        {
                            "paragraph": {
                                "elements": [
                                    {"textRun": {"content": "Bold text here"}}
                                ]
                            }
                        }
                    ]
                }
            }

            from src.google_drive.client import GoogleDriveClient
            client = GoogleDriveClient()
            result = await client.format_text(
                "doc_123",
                text_to_find="Bold",
                bold=True,
            )

            assert result is True
            mock_api.format_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_doc_content(self, mock_services, mock_credentials):
        """Test getting document content."""
        drive_service, docs_service = mock_services

        with patch("src.google_drive.client.get_credentials", return_value=mock_credentials), \
             patch("src.google_drive.client.api") as mock_api:
            mock_api.get_drive_service.return_value = drive_service
            mock_api.get_docs_service.return_value = docs_service
            mock_api.export_google_doc.return_value = "Plain content"

            from src.google_drive.client import GoogleDriveClient
            client = GoogleDriveClient()
            content = await client.get_doc_content("doc_123")

            assert content == "Plain content"

    @pytest.mark.asyncio
    async def test_get_doc_content_with_formatting(self, mock_services, mock_credentials):
        """Test getting document content with formatting info."""
        drive_service, docs_service = mock_services

        with patch("src.google_drive.client.get_credentials", return_value=mock_credentials), \
             patch("src.google_drive.client.api") as mock_api:
            mock_api.get_drive_service.return_value = drive_service
            mock_api.get_docs_service.return_value = docs_service
            mock_api.get_document.return_value = {
                "body": {
                    "content": [
                        {
                            "paragraph": {
                                "paragraphStyle": {"namedStyleType": "TITLE"},
                                "elements": [
                                    {"textRun": {"content": "Title\n", "textStyle": {"bold": True}}}
                                ]
                            }
                        }
                    ]
                }
            }

            from src.google_drive.client import GoogleDriveClient
            client = GoogleDriveClient()
            content = await client.get_doc_content("doc_123", include_formatting=True)

            assert "# " in content or "**" in content  # Should have formatting markers

    @pytest.mark.asyncio
    async def test_services_initialized_lazily(self, mock_services, mock_credentials):
        """Test that services are initialized lazily."""
        with patch("src.google_drive.client.get_credentials") as mock_get_creds, \
             patch("src.google_drive.client.api"):
            from src.google_drive.client import GoogleDriveClient
            client = GoogleDriveClient()

            # Credentials should not be loaded yet
            mock_get_creds.assert_not_called()

    @pytest.mark.asyncio
    async def test_services_reused(self, mock_services, mock_credentials):
        """Test that services are reused across calls."""
        drive_service, docs_service = mock_services

        with patch("src.google_drive.client.get_credentials", return_value=mock_credentials) as mock_get_creds, \
             patch("src.google_drive.client.api") as mock_api:
            mock_api.get_drive_service.return_value = drive_service
            mock_api.get_docs_service.return_value = docs_service
            mock_api.list_files_in_folder.return_value = []
            mock_api.export_google_doc.return_value = ""

            from src.google_drive.client import GoogleDriveClient
            client = GoogleDriveClient()

            await client.list_folder("folder1")
            await client.list_folder("folder2")
            await client.read_google_doc("doc1")

            # Credentials should only be loaded once
            assert mock_get_creds.call_count == 1


class TestFindTextRange:
    """Tests for _find_text_range helper method."""

    def test_finds_text_at_beginning(self):
        """Test finding text at the beginning of document."""
        doc = {
            "body": {
                "content": [
                    {
                        "paragraph": {
                            "elements": [
                                {"textRun": {"content": "Hello World"}}
                            ]
                        }
                    }
                ]
            }
        }

        from src.google_drive.client import GoogleDriveClient
        client = GoogleDriveClient()
        start, end = client._find_text_range(doc, "Hello")

        assert start == 1  # Document body starts at index 1
        assert end == 6

    def test_finds_nth_instance(self):
        """Test finding nth instance of text."""
        doc = {
            "body": {
                "content": [
                    {
                        "paragraph": {
                            "elements": [
                                {"textRun": {"content": "Hello Hello Hello"}}
                            ]
                        }
                    }
                ]
            }
        }

        from src.google_drive.client import GoogleDriveClient
        client = GoogleDriveClient()

        # Find second instance
        start, end = client._find_text_range(doc, "Hello", instance=2)
        assert start == 7
        assert end == 12

    def test_returns_none_when_not_found(self):
        """Test returning None when text is not found."""
        doc = {
            "body": {
                "content": [
                    {
                        "paragraph": {
                            "elements": [
                                {"textRun": {"content": "Hello World"}}
                            ]
                        }
                    }
                ]
            }
        }

        from src.google_drive.client import GoogleDriveClient
        client = GoogleDriveClient()
        start, end = client._find_text_range(doc, "NotFound")

        assert start is None
        assert end is None
