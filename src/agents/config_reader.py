"""ConfigReaderAgent - reads and validates configuration."""

import re
from pathlib import Path
from typing import Any

import yaml

from src.agents.base import BaseAgent
from src.models import ConfigOutput


class ConfigReaderAgent(BaseAgent):
    """Agent that reads and validates configuration from config.yaml."""

    agent_name = "config_reader"

    def run(self, config_path: str = "config.yaml") -> ConfigOutput:
        """Read and validate configuration.

        Args:
            config_path: Path to config file.

        Returns:
            Validated ConfigOutput.

        Raises:
            FileNotFoundError: If config file doesn't exist.
            ValueError: If config is invalid.
        """
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(path, encoding="utf-8") as f:
            raw_config = yaml.safe_load(f)

        # Apply defaults
        config = self._apply_defaults(raw_config or {})

        # Validate
        self._validate(config)

        # Extract folder IDs from URLs if needed
        config["source_folders"] = [
            self._extract_folder_id(f) for f in config.get("source_folders", [])
        ]
        if config.get("output_folder"):
            config["output_folder"] = self._extract_folder_id(config["output_folder"])

        # Flatten nested config
        format_config = config.get("format", {})
        content_config = config.get("content", {})

        return ConfigOutput(
            source_folders=config["source_folders"],
            output_folder=config.get("output_folder"),
            max_pages=format_config.get("max_pages", 2),
            language=format_config.get("language", "en"),
            style=format_config.get("style", "modern"),
            template=format_config.get("template", "chronological"),
            include_photo=content_config.get("include_photo", False),
            contact_info=content_config.get("contact_info", ["email", "phone", "linkedin"]),
            other_instructions=config.get("other_instructions"),
        )

    def _apply_defaults(self, config: dict[str, Any]) -> dict[str, Any]:
        """Apply default values to config.

        Args:
            config: Raw config dict.

        Returns:
            Config with defaults applied.
        """
        defaults = {
            "output_folder": None,
            "format": {
                "max_pages": 2,
                "language": "en",
                "style": "modern",
                "template": "chronological",
            },
            "content": {
                "include_photo": False,
                "contact_info": ["email", "phone", "linkedin"],
            },
            "other_instructions": None,
        }

        # Deep merge
        result = defaults.copy()
        for key, value in config.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = {**result[key], **value}
            else:
                result[key] = value

        return result

    def _validate(self, config: dict[str, Any]) -> None:
        """Validate configuration.

        Args:
            config: Config dict to validate.

        Raises:
            ValueError: If config is invalid.
        """
        # Required fields
        if not config.get("source_folders"):
            raise ValueError("source_folders is required in config.yaml")

        format_config = config.get("format", {})

        # Validate style
        valid_styles = ["formal", "modern", "creative", "technical"]
        style = format_config.get("style", "modern")
        if style not in valid_styles:
            raise ValueError(f"Invalid style '{style}'. Must be one of: {valid_styles}")

        # Validate template
        valid_templates = ["chronological", "functional", "combination"]
        template = format_config.get("template", "chronological")
        if template not in valid_templates:
            raise ValueError(f"Invalid template '{template}'. Must be one of: {valid_templates}")

        # Validate max_pages
        max_pages = format_config.get("max_pages", 2)
        if max_pages not in [1, 2, 3]:
            raise ValueError("max_pages must be 1, 2, or 3")

    def _extract_folder_id(self, folder_ref: str) -> str:
        """Extract folder ID from URL or return as-is.

        Args:
            folder_ref: Folder URL or ID.

        Returns:
            Folder ID.
        """
        # Match Google Drive folder URL
        match = re.search(r"/folders/([a-zA-Z0-9_-]+)", folder_ref)
        if match:
            return match.group(1)

        # Already an ID
        return folder_ref
