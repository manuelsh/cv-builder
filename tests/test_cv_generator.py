"""Tests for CVGeneratorAgent."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.cv_generator import CVGeneratorAgent
from src.models import (
    ConfigOutput,
    MaterialsOutput,
    JobAnalysisOutput,
    CVContentOutput,
)


class TestCVGeneratorAgent:
    """Tests for CVGeneratorAgent."""

    @pytest.fixture
    def mock_llm_client(self):
        """Create a mock LLM client."""
        client = MagicMock()
        client.complete = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_generate_cv_content(
        self, mock_llm_client, sample_config, sample_materials, sample_job_analysis
    ):
        """Test generating CV content."""
        mock_llm_client.complete.return_value = '''```json
{
    "name": "John Doe",
    "contact": {
        "email": "john@example.com",
        "phone": "+34 612 345 678",
        "linkedin": "linkedin.com/in/johndoe"
    },
    "summary": "Experienced ML Engineer with 8+ years building production ML systems.",
    "experience": [
        {
            "title": "Senior ML Engineer",
            "company": "TechCorp",
            "location": "Barcelona",
            "start_date": "Jan 2020",
            "end_date": null,
            "achievements": [
                "Led team of 5 engineers",
                "Reduced latency by 40%"
            ]
        }
    ],
    "education": [
        {
            "degree": "MSc Computer Science",
            "institution": "UPC",
            "year": "2016",
            "details": null
        }
    ],
    "skills": {
        "categories": {
            "Technical": ["Python", "PyTorch", "AWS"],
            "Leadership": ["Team management"]
        }
    },
    "awards": null,
    "additional": ["Languages: Spanish (native)"],
    "estimated_pages": 2
}
```'''

        agent = CVGeneratorAgent(llm_client=mock_llm_client)
        result = await agent.run(
            config=sample_config,
            materials=sample_materials,
            job_analysis=sample_job_analysis,
        )

        assert isinstance(result, CVContentOutput)
        assert result.name == "John Doe"
        assert result.contact.email == "john@example.com"
        assert len(result.experience) == 1
        assert result.experience[0].title == "Senior ML Engineer"
        assert result.style_applied == "modern"
        assert result.template_applied == "chronological"
        assert result.language == "en"

    @pytest.mark.asyncio
    async def test_applies_config_style(
        self, mock_llm_client, sample_materials, sample_job_analysis
    ):
        """Test that config style is applied."""
        mock_llm_client.complete.return_value = '''```json
{
    "name": "Test User",
    "contact": {},
    "summary": "Summary",
    "experience": [],
    "education": [],
    "skills": {"categories": {}},
    "awards": null,
    "additional": null,
    "estimated_pages": 1
}
```'''

        config = ConfigOutput(
            source_folders=["folder_1"],
            style="technical",
            template="functional",
            language="es",
        )

        agent = CVGeneratorAgent(llm_client=mock_llm_client)
        result = await agent.run(
            config=config,
            materials=sample_materials,
            job_analysis=sample_job_analysis,
        )

        assert result.style_applied == "technical"
        assert result.template_applied == "functional"
        assert result.language == "es"

    @pytest.mark.asyncio
    async def test_includes_other_instructions_in_prompt(
        self, mock_llm_client, sample_materials, sample_job_analysis
    ):
        """Test that other_instructions are included in the prompt."""
        mock_llm_client.complete.return_value = '''```json
{
    "name": "Test",
    "contact": {},
    "summary": "Test",
    "experience": [],
    "education": [],
    "skills": {"categories": {}},
    "awards": null,
    "additional": null,
    "estimated_pages": 1
}
```'''

        config = ConfigOutput(
            source_folders=["folder_1"],
            other_instructions="Always highlight Python\nKeep it short",
        )

        agent = CVGeneratorAgent(llm_client=mock_llm_client)
        await agent.run(
            config=config,
            materials=sample_materials,
            job_analysis=sample_job_analysis,
        )

        # Check that the prompt included the instructions
        call_args = mock_llm_client.complete.call_args
        messages = call_args[0][0]
        user_message = next(m for m in messages if m["role"] == "user")
        assert "Always highlight Python" in user_message["content"]

    @pytest.mark.asyncio
    async def test_handles_empty_materials(self, mock_llm_client, sample_config, sample_job_analysis):
        """Test handling of empty materials."""
        mock_llm_client.complete.return_value = '''```json
{
    "name": "Unknown",
    "contact": {},
    "summary": "No materials provided",
    "experience": [],
    "education": [],
    "skills": {"categories": {}},
    "awards": null,
    "additional": null,
    "estimated_pages": 1
}
```'''

        empty_materials = MaterialsOutput(documents=[], total_documents=0)

        agent = CVGeneratorAgent(llm_client=mock_llm_client)
        result = await agent.run(
            config=sample_config,
            materials=empty_materials,
            job_analysis=sample_job_analysis,
        )

        assert result.name == "Unknown"

    @pytest.mark.asyncio
    async def test_handles_invalid_json(self, mock_llm_client, sample_config, sample_materials, sample_job_analysis):
        """Test handling of invalid JSON from LLM."""
        mock_llm_client.complete.return_value = "Not valid JSON"

        agent = CVGeneratorAgent(llm_client=mock_llm_client)

        with pytest.raises(ValueError, match="Invalid JSON"):
            await agent.run(
                config=sample_config,
                materials=sample_materials,
                job_analysis=sample_job_analysis,
            )

    def test_build_user_prompt_includes_job_info(self, sample_config, sample_materials, sample_job_analysis):
        """Test that user prompt includes job information."""
        agent = CVGeneratorAgent()
        prompt = agent._build_user_prompt(sample_config, sample_materials, sample_job_analysis)

        assert "Senior Machine Learning Engineer" in prompt
        assert "TechCorp AI" in prompt
        assert "Python" in prompt

    def test_build_user_prompt_includes_materials(self, sample_config, sample_materials, sample_job_analysis):
        """Test that user prompt includes user materials."""
        agent = CVGeneratorAgent()
        prompt = agent._build_user_prompt(sample_config, sample_materials, sample_job_analysis)

        # Should include content from materials
        assert "Resume" in prompt or "John Doe" in prompt

    def test_build_user_prompt_includes_config(self, sample_config, sample_materials, sample_job_analysis):
        """Test that user prompt includes configuration."""
        agent = CVGeneratorAgent()
        prompt = agent._build_user_prompt(sample_config, sample_materials, sample_job_analysis)

        assert "modern" in prompt.lower()
        assert "2" in prompt  # max_pages
        assert "en" in prompt  # language


class TestCVGeneratorIntegration:
    """Integration tests for CVGeneratorAgent (require real LLM)."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_real_cv_generation(self, sample_config, sample_materials, sample_job_analysis):
        """Test with real LLM - requires .env configuration."""
        agent = CVGeneratorAgent()
        result = await agent.run(
            config=sample_config,
            materials=sample_materials,
            job_analysis=sample_job_analysis,
        )

        # Basic validation
        assert result.name is not None
        assert len(result.summary) > 0
