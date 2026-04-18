"""Tests for ConfigReaderAgent."""

from pathlib import Path
import tempfile

import pytest
import yaml

from src.agents.config_reader import ConfigReaderAgent
from src.models import ConfigOutput


class TestConfigReaderAgent:
    """Tests for ConfigReaderAgent."""

    def test_read_valid_config(self, sample_config_path: Path):
        """Test reading a valid config file."""
        agent = ConfigReaderAgent()
        config = agent.run(str(sample_config_path))

        assert isinstance(config, ConfigOutput)
        assert config.source_folders == ["folder_id_1", "folder_id_2"]
        assert config.output_folder == "output_folder_id"
        assert config.max_pages == 2
        assert config.language == "en"
        assert config.style == "modern"
        assert config.template == "chronological"
        assert config.include_photo is False
        assert "email" in config.contact_info
        assert config.other_instructions is not None

    def test_read_minimal_config(self):
        """Test reading a config with only required fields."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump({"source_folders": ["folder_123"]}, f)
            f.flush()

            agent = ConfigReaderAgent()
            config = agent.run(f.name)

            assert config.source_folders == ["folder_123"]
            # Check defaults
            assert config.output_folder is None
            assert config.max_pages == 2
            assert config.language == "en"
            assert config.style == "modern"
            assert config.template == "chronological"

    def test_missing_source_folders_raises_error(self):
        """Test that missing source_folders raises ValueError."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump({"output_folder": "some_folder"}, f)
            f.flush()

            agent = ConfigReaderAgent()
            with pytest.raises(ValueError, match="source_folders is required"):
                agent.run(f.name)

    def test_invalid_style_raises_error(self):
        """Test that invalid style raises ValueError."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump({
                "source_folders": ["folder_123"],
                "format": {"style": "invalid_style"},
            }, f)
            f.flush()

            agent = ConfigReaderAgent()
            with pytest.raises(ValueError, match="Invalid style"):
                agent.run(f.name)

    def test_invalid_template_raises_error(self):
        """Test that invalid template raises ValueError."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump({
                "source_folders": ["folder_123"],
                "format": {"template": "invalid_template"},
            }, f)
            f.flush()

            agent = ConfigReaderAgent()
            with pytest.raises(ValueError, match="Invalid template"):
                agent.run(f.name)

    def test_invalid_max_pages_raises_error(self):
        """Test that invalid max_pages raises ValueError."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump({
                "source_folders": ["folder_123"],
                "format": {"max_pages": 5},
            }, f)
            f.flush()

            agent = ConfigReaderAgent()
            with pytest.raises(ValueError, match="max_pages must be 1, 2, or 3"):
                agent.run(f.name)

    def test_file_not_found_raises_error(self):
        """Test that missing file raises FileNotFoundError."""
        agent = ConfigReaderAgent()
        with pytest.raises(FileNotFoundError):
            agent.run("nonexistent_file.yaml")

    def test_extract_folder_id_from_url(self):
        """Test extracting folder ID from Google Drive URL."""
        agent = ConfigReaderAgent()

        # Full URL
        url = "https://drive.google.com/drive/folders/1abc123xyz"
        assert agent._extract_folder_id(url) == "1abc123xyz"

        # Just an ID
        folder_id = "1abc123xyz"
        assert agent._extract_folder_id(folder_id) == "1abc123xyz"

    def test_all_styles_valid(self):
        """Test that all valid styles are accepted."""
        valid_styles = ["formal", "modern", "creative", "technical"]

        for style in valid_styles:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
                yaml.dump({
                    "source_folders": ["folder_123"],
                    "format": {"style": style},
                }, f)
                f.flush()

                agent = ConfigReaderAgent()
                config = agent.run(f.name)
                assert config.style == style

    def test_all_templates_valid(self):
        """Test that all valid templates are accepted."""
        valid_templates = ["chronological", "functional", "combination"]

        for template in valid_templates:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
                yaml.dump({
                    "source_folders": ["folder_123"],
                    "format": {"template": template},
                }, f)
                f.flush()

                agent = ConfigReaderAgent()
                config = agent.run(f.name)
                assert config.template == template
