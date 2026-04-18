"""Tests for Google Drive API wrappers."""

from unittest.mock import MagicMock, patch

import pytest


class TestGetServices:
    """Tests for service creation functions."""

    def test_get_drive_service(self):
        """Test creating Drive service."""
        mock_creds = MagicMock()

        with patch("src.google_drive.api.build") as mock_build:
            mock_build.return_value = MagicMock()

            from src.google_drive.api import get_drive_service
            service = get_drive_service(mock_creds)

            mock_build.assert_called_once_with("drive", "v3", credentials=mock_creds)
            assert service is not None

    def test_get_docs_service(self):
        """Test creating Docs service."""
        mock_creds = MagicMock()

        with patch("src.google_drive.api.build") as mock_build:
            mock_build.return_value = MagicMock()

            from src.google_drive.api import get_docs_service
            service = get_docs_service(mock_creds)

            mock_build.assert_called_once_with("docs", "v1", credentials=mock_creds)
            assert service is not None


class TestListFilesInFolder:
    """Tests for list_files_in_folder function."""

    @pytest.fixture
    def mock_drive_service(self):
        """Create mock Drive service."""
        service = MagicMock()
        return service

    def test_lists_files_in_folder(self, mock_drive_service):
        """Test listing files in a folder."""
        mock_drive_service.files().list().execute.return_value = {
            "files": [
                {"id": "doc1", "name": "Resume.gdoc", "mimeType": "application/vnd.google-apps.document"},
                {"id": "doc2", "name": "Cover.gdoc", "mimeType": "application/vnd.google-apps.document"},
            ]
        }

        from src.google_drive.api import list_files_in_folder
        files = list_files_in_folder(mock_drive_service, "folder_123")

        assert len(files) == 2
        assert files[0]["name"] == "Resume.gdoc"

    def test_returns_empty_list_for_empty_folder(self, mock_drive_service):
        """Test returning empty list for empty folder."""
        mock_drive_service.files().list().execute.return_value = {"files": []}

        from src.google_drive.api import list_files_in_folder
        files = list_files_in_folder(mock_drive_service, "empty_folder")

        assert files == []

    def test_uses_correct_query(self, mock_drive_service):
        """Test that correct query is used."""
        mock_drive_service.files().list().execute.return_value = {"files": []}

        from src.google_drive.api import list_files_in_folder
        list_files_in_folder(mock_drive_service, "folder_123")

        call_args = mock_drive_service.files().list.call_args
        assert "'folder_123' in parents" in call_args[1]["q"]
        assert "trashed = false" in call_args[1]["q"]


class TestExportGoogleDoc:
    """Tests for export_google_doc function."""

    @pytest.fixture
    def mock_drive_service(self):
        """Create mock Drive service."""
        service = MagicMock()
        return service

    def test_exports_as_plain_text(self, mock_drive_service):
        """Test exporting document as plain text."""
        mock_drive_service.files().export().execute.return_value = b"Document content"

        from src.google_drive.api import export_google_doc
        content = export_google_doc(mock_drive_service, "doc_123", "text/plain")

        assert content == "Document content"
        mock_drive_service.files().export.assert_called_with(
            fileId="doc_123",
            mimeType="text/plain",
        )

    def test_exports_as_html(self, mock_drive_service):
        """Test exporting document as HTML."""
        mock_drive_service.files().export().execute.return_value = b"<html>Content</html>"

        from src.google_drive.api import export_google_doc
        content = export_google_doc(mock_drive_service, "doc_123", "text/html")

        assert "<html>" in content


class TestDownloadFile:
    """Tests for download_file function."""

    @pytest.fixture
    def mock_drive_service(self):
        """Create mock Drive service."""
        service = MagicMock()
        return service

    def test_downloads_file_content(self, mock_drive_service):
        """Test downloading file content."""
        mock_drive_service.files().get_media().execute.return_value = b"File content"

        from src.google_drive.api import download_file
        content = download_file(mock_drive_service, "file_123")

        assert content == "File content"

    def test_handles_string_response(self, mock_drive_service):
        """Test handling string response."""
        mock_drive_service.files().get_media().execute.return_value = "Already a string"

        from src.google_drive.api import download_file
        content = download_file(mock_drive_service, "file_123")

        assert content == "Already a string"


class TestCreateGoogleDoc:
    """Tests for create_google_doc function."""

    @pytest.fixture
    def mock_docs_service(self):
        """Create mock Docs service."""
        service = MagicMock()
        service.documents().create().execute.return_value = {"documentId": "new_doc_123"}
        return service

    @pytest.fixture
    def mock_drive_service(self):
        """Create mock Drive service."""
        service = MagicMock()
        return service

    def test_creates_document(self, mock_docs_service, mock_drive_service):
        """Test creating a new document."""
        from src.google_drive.api import create_google_doc
        result = create_google_doc(
            mock_docs_service,
            mock_drive_service,
            "Test Doc",
            "Content",
            None,
        )

        assert result["id"] == "new_doc_123"
        assert "docs.google.com" in result["url"]
        # Verify create was called with correct title
        mock_docs_service.documents().create.assert_called_with(body={"title": "Test Doc"})

    def test_moves_to_folder(self, mock_docs_service, mock_drive_service):
        """Test moving document to specified folder."""
        from src.google_drive.api import create_google_doc
        create_google_doc(
            mock_docs_service,
            mock_drive_service,
            "Test Doc",
            "Content",
            "parent_folder_123",
        )

        mock_drive_service.files().update.assert_called_once()
        call_args = mock_drive_service.files().update.call_args
        assert call_args[1]["addParents"] == "parent_folder_123"

    def test_inserts_content(self, mock_docs_service, mock_drive_service):
        """Test inserting content into document."""
        from src.google_drive.api import create_google_doc
        create_google_doc(
            mock_docs_service,
            mock_drive_service,
            "Test Doc",
            "Hello World",
            None,
        )

        mock_docs_service.documents().batchUpdate.assert_called_once()
        call_args = mock_docs_service.documents().batchUpdate.call_args
        requests = call_args[1]["body"]["requests"]
        assert requests[0]["insertText"]["text"] == "Hello World"


class TestFormatParagraph:
    """Tests for format_paragraph function."""

    @pytest.fixture
    def mock_docs_service(self):
        """Create mock Docs service."""
        service = MagicMock()
        return service

    def test_applies_paragraph_style(self, mock_docs_service):
        """Test applying paragraph style."""
        from src.google_drive.api import format_paragraph
        format_paragraph(
            mock_docs_service,
            "doc_123",
            start_index=1,
            end_index=10,
            style={"namedStyleType": "HEADING_1"},
        )

        mock_docs_service.documents().batchUpdate.assert_called_once()
        call_args = mock_docs_service.documents().batchUpdate.call_args
        assert call_args[1]["documentId"] == "doc_123"


class TestFormatText:
    """Tests for format_text function."""

    @pytest.fixture
    def mock_docs_service(self):
        """Create mock Docs service."""
        service = MagicMock()
        return service

    def test_applies_text_style(self, mock_docs_service):
        """Test applying text style."""
        from src.google_drive.api import format_text
        format_text(
            mock_docs_service,
            "doc_123",
            start_index=1,
            end_index=10,
            style={"bold": True},
        )

        mock_docs_service.documents().batchUpdate.assert_called_once()


class TestGetDocument:
    """Tests for get_document function."""

    @pytest.fixture
    def mock_docs_service(self):
        """Create mock Docs service."""
        service = MagicMock()
        service.documents().get().execute.return_value = {
            "documentId": "doc_123",
            "title": "Test Doc",
            "body": {"content": []},
        }
        return service

    def test_gets_document(self, mock_docs_service):
        """Test getting document."""
        from src.google_drive.api import get_document
        doc = get_document(mock_docs_service, "doc_123")

        assert doc["documentId"] == "doc_123"
        mock_docs_service.documents().get.assert_called_with(documentId="doc_123")
