"""Tests for JobAnalyzerAgent."""

from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from src.agents.job_analyzer import JobAnalyzerAgent
from src.models import JobAnalysisOutput


class TestJobAnalyzerAgent:
    """Tests for JobAnalyzerAgent."""

    @pytest.fixture
    def mock_llm_client(self):
        """Create a mock LLM client."""
        client = MagicMock()
        client.complete = AsyncMock()
        return client

    def test_detect_url_input(self):
        """Test detection of URL input type."""
        agent = JobAnalyzerAgent()

        assert agent._detect_input_type("https://linkedin.com/jobs/123") == "url"
        assert agent._detect_input_type("http://example.com/job") == "url"

    def test_detect_file_input(self, sample_job_posting_path):
        """Test detection of file input type."""
        agent = JobAnalyzerAgent()

        assert agent._detect_input_type(str(sample_job_posting_path)) == "file"

    def test_detect_description_input(self):
        """Test detection of description input type."""
        agent = JobAnalyzerAgent()

        # Plain text that's not a URL or file
        assert agent._detect_input_type("Senior Python Developer at startup") == "description"
        assert agent._detect_input_type("Looking for ML Engineer with 5 years exp") == "description"

    @pytest.mark.asyncio
    async def test_analyze_from_file(self, mock_llm_client, sample_job_posting_path):
        """Test analyzing job from file."""
        mock_llm_client.complete.return_value = '''```json
{
    "job_title": "Senior Machine Learning Engineer",
    "company_name": "TechCorp AI",
    "location": "Barcelona, Spain",
    "job_type": "Full-time",
    "required_skills": ["Python", "PyTorch", "MLOps"],
    "nice_to_have_skills": ["PhD", "Kubernetes"],
    "responsibilities": ["Design ML models", "Build pipelines"],
    "qualifications": ["MSc in CS"],
    "company_culture": null,
    "industry": "AI/Technology",
    "salary_range": "€80,000 - €120,000"
}
```'''

        agent = JobAnalyzerAgent(llm_client=mock_llm_client)
        result = await agent.run(str(sample_job_posting_path))

        assert isinstance(result, JobAnalysisOutput)
        assert result.job_title == "Senior Machine Learning Engineer"
        assert result.company_name == "TechCorp AI"
        assert result.source_type == "file"
        assert "Python" in result.required_skills

    @pytest.mark.asyncio
    async def test_analyze_from_description(self, mock_llm_client):
        """Test analyzing job from plain description."""
        mock_llm_client.complete.return_value = '''```json
{
    "job_title": "Python Developer",
    "company_name": null,
    "location": null,
    "job_type": null,
    "required_skills": ["Python"],
    "nice_to_have_skills": [],
    "responsibilities": [],
    "qualifications": [],
    "company_culture": null,
    "industry": "Technology",
    "salary_range": null
}
```'''

        agent = JobAnalyzerAgent(llm_client=mock_llm_client)
        result = await agent.run("Python Developer at startup")

        assert result.job_title == "Python Developer"
        assert result.source_type == "description"

    @pytest.mark.asyncio
    async def test_analyze_from_url(self, mock_llm_client):
        """Test analyzing job from URL."""
        mock_llm_client.complete.return_value = '''```json
{
    "job_title": "Software Engineer",
    "company_name": "Tech Company",
    "location": "Remote",
    "job_type": "Full-time",
    "required_skills": ["JavaScript", "React"],
    "nice_to_have_skills": [],
    "responsibilities": [],
    "qualifications": [],
    "company_culture": null,
    "industry": null,
    "salary_range": null
}
```'''

        with patch.object(JobAnalyzerAgent, "_fetch_url", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = "Job posting content..."

            agent = JobAnalyzerAgent(llm_client=mock_llm_client)
            result = await agent.run("https://example.com/job/123")

            assert result.source_type == "url"
            mock_fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_json_without_code_blocks(self, mock_llm_client):
        """Test that agent handles JSON without markdown code blocks."""
        mock_llm_client.complete.return_value = '''{
    "job_title": "Data Scientist",
    "company_name": "DataCo",
    "location": null,
    "job_type": null,
    "required_skills": ["Python", "SQL"],
    "nice_to_have_skills": [],
    "responsibilities": [],
    "qualifications": [],
    "company_culture": null,
    "industry": null,
    "salary_range": null
}'''

        agent = JobAnalyzerAgent(llm_client=mock_llm_client)
        result = await agent.run("Data Scientist role")

        assert result.job_title == "Data Scientist"

    @pytest.mark.asyncio
    async def test_handles_invalid_json_gracefully(self, mock_llm_client):
        """Test that agent handles invalid JSON from LLM."""
        mock_llm_client.complete.return_value = "This is not valid JSON"

        agent = JobAnalyzerAgent(llm_client=mock_llm_client)

        with pytest.raises(ValueError, match="Invalid JSON"):
            await agent.run("Some job description")

    @pytest.mark.asyncio
    async def test_preserves_raw_description(self, mock_llm_client, sample_job_posting_path, sample_job_posting_text):
        """Test that raw description is preserved in output."""
        mock_llm_client.complete.return_value = '''```json
{
    "job_title": "Test",
    "company_name": null,
    "location": null,
    "job_type": null,
    "required_skills": [],
    "nice_to_have_skills": [],
    "responsibilities": [],
    "qualifications": [],
    "company_culture": null,
    "industry": null,
    "salary_range": null
}
```'''

        agent = JobAnalyzerAgent(llm_client=mock_llm_client)
        result = await agent.run(str(sample_job_posting_path))

        assert result.raw_description == sample_job_posting_text

    def test_nonexistent_path_detected_as_description(self, mock_llm_client):
        """Test that non-existent paths are treated as descriptions."""
        # Since Path.exists() returns False for non-existent paths,
        # they are treated as descriptions, not files
        agent = JobAnalyzerAgent(llm_client=mock_llm_client)
        input_type = agent._detect_input_type("/nonexistent/path/job.txt")
        assert input_type == "description"

    def test_extracts_text_from_google_careers_html(self, mock_llm_client, google_careers_html):
        """Test extraction from a recorded Google Careers page shape."""
        agent = JobAnalyzerAgent(llm_client=mock_llm_client)
        text = agent._extract_text_from_html(google_careers_html)

        assert "Senior Software Engineering Manager" in text
        assert "Minimum qualifications:" in text
        assert "Preferred qualifications:" in text
        assert "Responsibilities" in text
        assert "agentize security analyst workflows" in text


class TestJobAnalyzerIntegration:
    """Integration tests for JobAnalyzerAgent (require real LLM)."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_real_job_analysis(self, sample_job_posting_path):
        """Test with real LLM - requires .env configuration."""
        agent = JobAnalyzerAgent()
        result = await agent.run(str(sample_job_posting_path))

        # Basic validation
        assert result.job_title is not None
        assert len(result.required_skills) > 0
