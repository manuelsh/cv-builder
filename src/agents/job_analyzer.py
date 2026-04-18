"""JobAnalyzerAgent - analyzes job postings to extract requirements."""

from pathlib import Path
from typing import Any

import httpx

from src.agents.base import BaseAgent
from src.models import JobAnalysisOutput


JOB_ANALYZER_PROMPT = """You are a job posting analyzer. Your task is to extract structured information from job descriptions to enable CV tailoring.

Analyze the provided job posting and extract all relevant information.

Your analysis should identify:

1. **Basic Information**
   - Job title (exact as stated)
   - Company name
   - Location (city, country, remote options)
   - Job type (full-time, contract, etc.)

2. **Requirements**
   - Required skills (must-have, explicitly stated)
   - Nice-to-have skills (preferred, bonus points)
   - Years of experience required
   - Education requirements

3. **Role Details**
   - Key responsibilities
   - Qualifications mentioned

4. **Company Context**
   - Industry
   - Company culture indicators

5. **Compensation** (if available)
   - Salary range

## Output Format

Return a JSON object with this structure:

```json
{
  "job_title": "string",
  "company_name": "string or null",
  "location": "string or null",
  "job_type": "string or null",
  "required_skills": ["skill1", "skill2"],
  "nice_to_have_skills": ["skill1", "skill2"],
  "responsibilities": ["resp1", "resp2"],
  "qualifications": ["qual1", "qual2"],
  "company_culture": "string or null",
  "industry": "string or null",
  "salary_range": "string or null"
}
```

## Important Notes

- Extract skills as specific as possible (e.g., "Python" not "programming")
- Distinguish between required and nice-to-have clearly
- If information is not available, use null
- Preserve exact job title wording for keyword matching
"""


class JobAnalyzerAgent(BaseAgent):
    """Agent that analyzes job postings to extract requirements."""

    agent_name = "job_analyzer"

    @property
    def requires_llm(self) -> bool:
        return True

    async def run(self, job_target: str) -> JobAnalysisOutput:
        """Analyze job target and extract requirements.

        Args:
            job_target: Job URL, file path, or description text.

        Returns:
            Structured job analysis.

        Raises:
            FileNotFoundError: If file path doesn't exist.
            ValueError: If LLM response is invalid.
        """
        # Detect input type and get raw content
        source_type = self._detect_input_type(job_target)
        raw_content = await self._fetch_job_content(job_target, source_type)

        # Build prompt
        user_content = f"""Analyze this job posting and extract structured information:

---
{raw_content}
---

Return the analysis as JSON matching the specified schema."""

        messages = self.build_messages(user_content, system_content=JOB_ANALYZER_PROMPT)
        response = await self.llm_client.complete(messages)

        result = await self.parse_json_response(response, JobAnalysisOutput)
        result.raw_description = raw_content
        result.source_type = source_type

        return result

    def _detect_input_type(self, job_target: str) -> str:
        """Detect the input type.

        Args:
            job_target: Input string.

        Returns:
            'url', 'file', or 'description'.
        """
        if job_target.startswith(("http://", "https://")):
            return "url"

        if Path(job_target).exists():
            return "file"

        return "description"

    async def _fetch_job_content(self, job_target: str, source_type: str) -> str:
        """Fetch job content based on input type.

        Args:
            job_target: Input string.
            source_type: Detected input type.

        Returns:
            Job posting text content.
        """
        if source_type == "url":
            return await self._fetch_url(job_target)
        elif source_type == "file":
            path = Path(job_target)
            if not path.exists():
                raise FileNotFoundError(f"File not found: {job_target}")
            return path.read_text(encoding="utf-8")
        else:
            return job_target

    async def _fetch_url(self, url: str) -> str:
        """Fetch and extract text from URL.

        Args:
            url: URL to fetch.

        Returns:
            Extracted text content.
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                follow_redirects=True,
                timeout=30.0,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
            )
            response.raise_for_status()

        return self._extract_text_from_html(response.text)

    def _extract_text_from_html(self, html: str) -> str:
        """Extract readable text from HTML.

        Args:
            html: HTML content.

        Returns:
            Extracted text.
        """
        # Simple text extraction - remove HTML tags
        import re

        # Remove script and style elements
        html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)

        # Remove HTML tags
        text = re.sub(r"<[^>]+>", " ", html)

        # Decode HTML entities
        text = text.replace("&nbsp;", " ")
        text = text.replace("&amp;", "&")
        text = text.replace("&lt;", "<")
        text = text.replace("&gt;", ">")
        text = text.replace("&quot;", '"')

        # Clean up whitespace
        text = re.sub(r"\s+", " ", text)
        text = "\n".join(line.strip() for line in text.split("\n") if line.strip())

        return text.strip()
