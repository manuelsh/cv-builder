"""Tests for DocFormatterAgent."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.doc_formatter import DocFormatterAgent
from src.models import ConfigOutput, CVContentOutput, DocFormatterOutput


class TestDocFormatterAgent:
    """Tests for DocFormatterAgent."""

    @pytest.fixture
    def mock_drive_client(self):
        """Create a mock Google Drive client."""
        client = MagicMock()
        client.create_google_doc = AsyncMock(return_value={
            "id": "doc_123",
            "url": "https://docs.google.com/document/d/doc_123/edit",
        })
        client.format_paragraph = AsyncMock()
        client.format_text = AsyncMock()
        client.get_doc_content = AsyncMock(return_value="style=bold")
        return client

    @pytest.mark.asyncio
    async def test_create_and_format_doc(self, mock_drive_client, sample_config, sample_cv_content):
        """Test creating and formatting a Google Doc."""
        agent = DocFormatterAgent(google_drive_client=mock_drive_client)
        result = await agent.run(config=sample_config, cv_content=sample_cv_content)

        assert isinstance(result, DocFormatterOutput)
        assert result.document_id == "doc_123"
        assert "docs.google.com" in result.document_url
        assert result.formatting_applied is True
        assert result.verification_passed is True

    @pytest.mark.asyncio
    async def test_doc_name_includes_name_and_date(self, mock_drive_client, sample_config, sample_cv_content):
        """Test that document name includes user name and date."""
        agent = DocFormatterAgent(google_drive_client=mock_drive_client)
        await agent.run(config=sample_config, cv_content=sample_cv_content)

        # Check the name passed to create_google_doc
        call_args = mock_drive_client.create_google_doc.call_args
        doc_name = call_args[1]["name"]

        assert "John Doe" in doc_name
        assert "CV" in doc_name

    @pytest.mark.asyncio
    async def test_uses_output_folder_from_config(self, mock_drive_client, sample_config, sample_cv_content):
        """Test that output folder from config is used."""
        agent = DocFormatterAgent(google_drive_client=mock_drive_client)
        await agent.run(config=sample_config, cv_content=sample_cv_content)

        call_args = mock_drive_client.create_google_doc.call_args
        assert call_args[1]["parent_folder_id"] == "output_folder_id"

    @pytest.mark.asyncio
    async def test_uses_first_source_folder_when_no_output(self, mock_drive_client, sample_cv_content):
        """Test that first source folder is used when output_folder is None."""
        config = ConfigOutput(
            source_folders=["folder_1", "folder_2"],
            output_folder=None,
        )

        agent = DocFormatterAgent(google_drive_client=mock_drive_client)
        await agent.run(config=config, cv_content=sample_cv_content)

        call_args = mock_drive_client.create_google_doc.call_args
        assert call_args[1]["parent_folder_id"] == "folder_1"

    @pytest.mark.asyncio
    async def test_applies_title_formatting(self, mock_drive_client, sample_config, sample_cv_content):
        """Test that name is formatted as title."""
        agent = DocFormatterAgent(google_drive_client=mock_drive_client)
        await agent.run(config=sample_config, cv_content=sample_cv_content)

        # Check format_paragraph was called for name with TITLE style
        calls = mock_drive_client.format_paragraph.call_args_list
        title_call = next(
            (c for c in calls if c[1].get("named_style_type") == "TITLE"),
            None
        )
        assert title_call is not None

    @pytest.mark.asyncio
    async def test_applies_heading_formatting(self, mock_drive_client, sample_config, sample_cv_content):
        """Test that section headers are formatted as headings."""
        agent = DocFormatterAgent(google_drive_client=mock_drive_client)
        await agent.run(config=sample_config, cv_content=sample_cv_content)

        # Check format_paragraph was called for sections
        calls = mock_drive_client.format_paragraph.call_args_list
        heading_calls = [c for c in calls if c[1].get("named_style_type") == "HEADING_1"]
        assert len(heading_calls) >= 1  # At least Summary section

    @pytest.mark.asyncio
    async def test_applies_bold_formatting(self, mock_drive_client, sample_config, sample_cv_content):
        """Test that job titles are formatted as bold."""
        agent = DocFormatterAgent(google_drive_client=mock_drive_client)
        await agent.run(config=sample_config, cv_content=sample_cv_content)

        # Check format_text was called with bold=True
        calls = mock_drive_client.format_text.call_args_list
        bold_calls = [c for c in calls if c[1].get("bold") is True]
        assert len(bold_calls) >= 1

    @pytest.mark.asyncio
    async def test_handles_formatting_error_gracefully(self, mock_drive_client, sample_config, sample_cv_content):
        """Test that formatting errors don't crash the agent."""
        mock_drive_client.format_paragraph.side_effect = Exception("Formatting failed")

        agent = DocFormatterAgent(google_drive_client=mock_drive_client)
        result = await agent.run(config=sample_config, cv_content=sample_cv_content)

        # Should still return a result
        assert result.document_id == "doc_123"
        assert result.formatting_applied is False
        assert len(result.formatting_errors) > 0

    @pytest.mark.asyncio
    async def test_verification_checks_formatting(self, mock_drive_client, sample_config, sample_cv_content):
        """Test that verification checks for applied formatting."""
        mock_drive_client.get_doc_content.return_value = "plain text without formatting"

        agent = DocFormatterAgent(google_drive_client=mock_drive_client)
        result = await agent.run(config=sample_config, cv_content=sample_cv_content)

        # Verification should fail if no formatting markers found
        assert result.verification_passed is False

    def test_generate_plain_text_includes_name(self, sample_cv_content):
        """Test that plain text includes name."""
        agent = DocFormatterAgent()
        text = agent._generate_plain_text(sample_cv_content)

        assert "John Doe" in text

    def test_generate_plain_text_includes_contact(self, sample_cv_content):
        """Test that plain text includes contact info."""
        agent = DocFormatterAgent()
        text = agent._generate_plain_text(sample_cv_content)

        assert "john.doe@email.com" in text

    def test_generate_plain_text_includes_summary(self, sample_cv_content):
        """Test that plain text includes summary."""
        agent = DocFormatterAgent()
        text = agent._generate_plain_text(sample_cv_content)

        assert "Experienced ML Engineer" in text

    def test_generate_plain_text_includes_experience(self, sample_cv_content):
        """Test that plain text includes experience."""
        agent = DocFormatterAgent()
        text = agent._generate_plain_text(sample_cv_content)

        assert "Senior ML Engineer" in text
        assert "TechCorp" in text
        assert "Led team of 5 engineers" in text

    def test_generate_plain_text_includes_sections(self, sample_cv_content):
        """Test that plain text includes section headers."""
        agent = DocFormatterAgent()
        text = agent._generate_plain_text(sample_cv_content)

        assert "Summary" in text
        assert "Experience" in text
        assert "Education" in text
        assert "Skills" in text


class TestDocFormatterIntegration:
    """Integration tests for DocFormatterAgent (require real Google Drive)."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_real_doc_creation(self, sample_config, sample_cv_content):
        """Test with real Google Drive - requires MCP configuration."""
        agent = DocFormatterAgent()
        result = await agent.run(config=sample_config, cv_content=sample_cv_content)

        assert result.document_id is not None
        assert "docs.google.com" in result.document_url
