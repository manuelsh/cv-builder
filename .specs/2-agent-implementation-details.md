**Status:** Draft
**Created:** 2026-03-17
**Purpose:** Detailed implementation specifications for each agent, including prompts and error handling.

---

# Specification 2: Agent Implementation Details

## 1. BaseAgent Class

All agents inherit from `BaseAgent`, providing common functionality:

```python
from abc import ABC, abstractmethod
from typing import Any, TypeVar
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

class BaseAgent(ABC):
    """Abstract base class for all CV builder agents."""

    agent_name: str = "base"

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        config: dict[str, Any] | None = None,
        agent_logger: AgentLogger | None = None,
    ):
        self.config = config or load_config()
        self.agent_logger = agent_logger

        if llm_client is None and self.requires_llm:
            model = get_model(self.agent_name, self.config)
            self.llm_client = LLMClient(default_model=model)
        else:
            self.llm_client = llm_client

    @property
    def requires_llm(self) -> bool:
        """Override in subclasses that need LLM."""
        return False

    def get_prompt(self) -> str:
        """Load prompt from prompts/agents/{agent_name}.md"""
        # Similar to theoria-agents implementation
        pass

    @abstractmethod
    async def run(self, **kwargs: Any) -> Any:
        """Execute the agent's task."""
        pass
```

---

## 2. ConfigReaderAgent

### 2.1 Implementation

```python
class ConfigReaderAgent(BaseAgent):
    agent_name = "config_reader"

    async def run(self, config_path: str = "config.yaml") -> ConfigOutput:
        """Read and validate configuration."""
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(path) as f:
            raw_config = yaml.safe_load(f)

        # Apply defaults
        config = self._apply_defaults(raw_config)

        # Validate
        self._validate(config)

        return ConfigOutput(**config)

    def _apply_defaults(self, config: dict) -> dict:
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
        # Deep merge with defaults
        return deep_merge(defaults, config)

    def _validate(self, config: dict) -> None:
        if not config.get("source_folders"):
            raise ValueError("source_folders is required in config.yaml")

        valid_styles = ["formal", "modern", "creative", "technical"]
        if config["format"]["style"] not in valid_styles:
            raise ValueError(f"Invalid style. Must be one of: {valid_styles}")

        valid_templates = ["chronological", "functional", "combination"]
        if config["format"]["template"] not in valid_templates:
            raise ValueError(f"Invalid template. Must be one of: {valid_templates}")
```

### 2.2 No Prompt Needed

This agent doesn't use LLM - it's pure configuration parsing.

---

## 3. MaterialsGathererAgent

### 3.1 Implementation

```python
class MaterialsGathererAgent(BaseAgent):
    agent_name = "materials_gatherer"

    def __init__(self, google_drive_client: GoogleDriveClient | None = None, **kwargs):
        super().__init__(**kwargs)
        self.drive = google_drive_client or GoogleDriveClient()

    async def run(self, config: ConfigOutput) -> MaterialsOutput:
        """Fetch all materials from Google Drive folders."""
        documents = []
        errors = []

        for folder_id in config.source_folders:
            try:
                folder_docs = await self._process_folder(folder_id)
                documents.extend(folder_docs)
            except Exception as e:
                errors.append(f"Error processing folder {folder_id}: {e}")

        return MaterialsOutput(
            documents=documents,
            total_documents=len(documents),
            extraction_errors=errors,
        )

    async def _process_folder(self, folder_id: str) -> list[DocumentContent]:
        """Process a single folder."""
        files = await self.drive.list_folder(folder_id)
        documents = []

        for file in files:
            try:
                doc = await self._read_file(file, folder_id)
                if doc:
                    documents.append(doc)
            except Exception as e:
                # Log error but continue with other files
                print(f"Warning: Could not read {file['name']}: {e}")

        return documents

    async def _read_file(self, file: dict, folder_id: str) -> DocumentContent | None:
        """Read a single file based on its type."""
        file_id = file["id"]
        file_name = file["name"]
        mime_type = file.get("mimeType", "")

        if "document" in mime_type:
            content = await self.drive.read_google_doc(file_id, format="markdown")
            file_type = "google_doc"
        elif file_name.endswith(".pdf"):
            # Convert PDF to text
            content = await self.drive.convert_pdf_to_text(file_id)
            file_type = "pdf"
        elif file_name.endswith((".txt", ".md")):
            content = await self.drive.download_file_content(file_id)
            file_type = "text"
        else:
            return None  # Skip unsupported file types

        return DocumentContent(
            source_folder=folder_id,
            file_name=file_name,
            file_type=file_type,
            content=content,
            metadata={"id": file_id, "mimeType": mime_type},
        )
```

### 3.2 No Prompt Needed

This agent uses MCP tools, not LLM.

---

## 4. JobAnalyzerAgent

### 4.1 Implementation

```python
class JobAnalyzerAgent(BaseAgent):
    agent_name = "job_analyzer"

    @property
    def requires_llm(self) -> bool:
        return True

    async def run(self, job_target: str) -> JobAnalysisOutput:
        """Analyze job target and extract requirements."""
        # Detect input type and get raw content
        source_type, raw_content = await self._fetch_job_content(job_target)

        # Build prompt
        user_content = f"""Analyze this job posting and extract structured information:

---
{raw_content}
---

Return the analysis as JSON matching the specified schema."""

        messages = self.build_messages(user_content)
        response = await self.llm_client.complete(messages)

        result = await self.parse_json_response(response, JobAnalysisOutput)
        result.raw_description = raw_content
        result.source_type = source_type

        return result

    async def _fetch_job_content(self, job_target: str) -> tuple[str, str]:
        """Fetch job content based on input type."""
        if job_target.startswith(("http://", "https://")):
            content = await self._fetch_url(job_target)
            return "url", content
        elif Path(job_target).exists():
            with open(job_target) as f:
                return "file", f.read()
        else:
            return "description", job_target

    async def _fetch_url(self, url: str) -> str:
        """Fetch and extract text from URL."""
        async with httpx.AsyncClient() as client:
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()

        # Extract text from HTML
        # Use simple extraction or LLM-based extraction
        return self._extract_text_from_html(response.text)
```

### 4.2 Prompt File: `prompts/agents/job_analyzer.md`

```markdown
# Agent: JobAnalyzer
**Version:** 1.0.0
**Last Updated:** 2026-03-17

## Role
You are a job posting analyzer. Your task is to extract structured information from job descriptions to enable CV tailoring.

## System Prompt

Analyze the provided job posting and extract all relevant information for CV tailoring.

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
   - Team structure hints
   - Reporting structure

4. **Company Context**
   - Industry
   - Company culture indicators
   - Growth stage (startup, enterprise, etc.)

5. **Compensation** (if available)
   - Salary range
   - Equity
   - Benefits mentioned

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
```

---

## 5. CVGeneratorAgent

### 5.1 Implementation

```python
class CVGeneratorAgent(BaseAgent):
    agent_name = "cv_generator"

    @property
    def requires_llm(self) -> bool:
        return True

    async def run(
        self,
        config: ConfigOutput,
        materials: MaterialsOutput,
        job_analysis: JobAnalysisOutput,
    ) -> CVContentOutput:
        """Generate tailored CV content."""
        # Build comprehensive prompt with all context
        user_content = self._build_user_prompt(config, materials, job_analysis)

        # Get style-specific system prompt
        system_prompt = self._get_styled_prompt(config.style, config.template)

        messages = self.build_messages(user_content, system_content=system_prompt)
        response = await self.llm_client.complete(messages)

        result = await self.parse_json_response(response, CVContentOutput)

        # Add metadata
        result.style_applied = config.style
        result.template_applied = config.template
        result.language = config.language

        return result

    def _build_user_prompt(
        self,
        config: ConfigOutput,
        materials: MaterialsOutput,
        job_analysis: JobAnalysisOutput,
    ) -> str:
        # Aggregate all user materials
        materials_text = "\n\n---\n\n".join(
            f"## {doc.file_name}\n{doc.content}"
            for doc in materials.documents
        )

        return f"""Generate a tailored CV for the following job:

## Target Job
- Title: {job_analysis.job_title}
- Company: {job_analysis.company_name or "Not specified"}
- Location: {job_analysis.location or "Not specified"}

### Required Skills
{chr(10).join(f"- {s}" for s in job_analysis.required_skills)}

### Nice-to-Have Skills
{chr(10).join(f"- {s}" for s in job_analysis.nice_to_have_skills)}

### Responsibilities
{chr(10).join(f"- {r}" for r in job_analysis.responsibilities)}

---

## User's Background Materials

{materials_text}

---

## Configuration

- **Language:** {config.language}
- **Max Pages:** {config.max_pages}
- **Style:** {config.style}
- **Template:** {config.template}
- **Contact Info to Include:** {", ".join(config.contact_info)}

{f"## Additional Instructions{chr(10)}{config.other_instructions}" if config.other_instructions else ""}

---

Generate a CV that:
1. Highlights experience and skills matching the job requirements
2. Uses the specified style and template
3. Fits within {config.max_pages} page(s)
4. Is written in {config.language}

Return the CV content as structured JSON."""

    def _get_styled_prompt(self, style: str, template: str) -> str:
        """Load style-specific prompt."""
        base_prompt = self.get_prompt()
        style_prompt = self._load_style_prompt(style)
        template_prompt = self._load_template_prompt(template)
        return f"{base_prompt}\n\n{style_prompt}\n\n{template_prompt}"
```

### 5.2 Prompt File: `prompts/agents/cv_generator.md`

```markdown
# Agent: CVGenerator
**Version:** 1.0.0
**Last Updated:** 2026-03-17

## Role
You are an expert CV writer who creates tailored, professional resumes that highlight relevant experience for specific job opportunities.

## System Prompt

Generate a professional CV tailored to the target job. Your CV should:

1. **Match the Job**: Prioritize experience and skills that align with job requirements
2. **Be Concise**: Use action verbs, quantify achievements, avoid fluff
3. **Be Honest**: Only include information from the provided materials
4. **Be Professional**: Follow industry standards for the specified style

## Content Guidelines

### Summary Section
- 2-3 sentences maximum
- Highlight most relevant experience for the target role
- Include years of experience and key strength areas
- Mention 1-2 achievements if space allows

### Experience Section
- Reverse chronological order (unless functional template)
- Use action verbs: Led, Built, Delivered, Achieved, Reduced, Increased
- Quantify achievements: percentages, dollar amounts, team sizes
- Focus on results, not just responsibilities
- 3-5 bullet points per role for recent positions

### Skills Section
- Group by category (Technical, Leadership, etc.)
- Prioritize skills mentioned in job requirements
- Be specific (Python, not "programming languages")

### Education Section
- Include degree, institution, year
- Add relevant details only if recent graduate or prestigious

@include base/cv_style_modern.md

## Output Format

Return a JSON object with this structure:

```json
{
  "name": "Full Name",
  "contact": {
    "email": "email@example.com",
    "phone": "+1234567890",
    "linkedin": "linkedin.com/in/name"
  },
  "summary": "2-3 sentence summary...",
  "experience": [
    {
      "title": "Job Title",
      "company": "Company Name",
      "location": "City, Country",
      "start_date": "Jan 2020",
      "end_date": "Present",
      "achievements": [
        "Achievement 1 with metrics",
        "Achievement 2 with impact"
      ]
    }
  ],
  "education": [
    {
      "degree": "MSc Computer Science",
      "institution": "University Name",
      "year": "2019",
      "details": "Relevant coursework or honors"
    }
  ],
  "skills": {
    "Technical": ["Python", "AWS", "Docker"],
    "Leadership": ["Team management", "Strategy"]
  },
  "awards": ["Award 1", "Award 2"],
  "additional": ["Language: Spanish (native)", "Publications: ..."]
}
```

## Important Notes

- Never invent information not in the source materials
- Keep within page limit by prioritizing recent/relevant experience
- Match keywords from job description where honest
- Use the language specified in configuration
```

### 5.3 Style Prompts: `prompts/base/cv_style_*.md`

**cv_style_modern.md:**
```markdown
## Modern Style Guidelines

- Clean, direct language with action verbs
- First person implied (no "I")
- Bullet points with measurable achievements
- Short, punchy sentences
- Minimal adjectives, maximum metrics
- Example: "Led 12-person team to 25% efficiency gain through process automation"
```

**cv_style_formal.md:**
```markdown
## Formal Style Guidelines

- Traditional, conservative language
- Full sentences, no contractions
- Third person or passive voice preferred
- Complete descriptions with context
- Example: "Managed a team of 12 professionals, achieving a 25% increase in departmental efficiency."
```

**cv_style_technical.md:**
```markdown
## Technical Style Guidelines

- Emphasis on technical skills, tools, methodologies
- Detailed specifications and metrics
- Include version numbers, stack details
- Acronyms acceptable (define on first use if uncommon)
- Example: "Architected microservices migration (K8s, Go, gRPC) for 12-engineer team; reduced deployment time 25%"
```

**cv_style_creative.md:**
```markdown
## Creative Style Guidelines

- Personality-driven, storytelling elements
- Can use unique formatting or narrative style
- Shows creativity through word choice
- Balance creativity with professionalism
- Example: "Transformed a struggling team of 12 into efficiency champions, slashing waste by 25%"
```

---

## 6. DocFormatterAgent

### 6.1 Implementation

```python
class DocFormatterAgent(BaseAgent):
    agent_name = "doc_formatter"

    def __init__(self, google_drive_client: GoogleDriveClient | None = None, **kwargs):
        super().__init__(**kwargs)
        self.drive = google_drive_client or GoogleDriveClient()

    async def run(
        self,
        config: ConfigOutput,
        cv_content: CVContentOutput,
    ) -> DocFormatterOutput:
        """Create and format Google Doc."""
        # Determine output folder
        output_folder = config.output_folder or config.source_folders[0]

        # Generate document name
        doc_name = self._generate_doc_name(cv_content)

        # Create document with plain text content
        plain_text = self._generate_plain_text(cv_content)
        doc = await self.drive.create_google_doc(
            name=doc_name,
            content=plain_text,
            parent_folder_id=output_folder,
        )

        doc_id = doc["id"]
        doc_url = doc["url"]

        # Apply formatting
        formatting_errors = []
        try:
            await self._apply_formatting(doc_id, cv_content)
        except Exception as e:
            formatting_errors.append(str(e))

        # Verify
        verification_passed = await self._verify_formatting(doc_id)

        return DocFormatterOutput(
            document_id=doc_id,
            document_url=doc_url,
            document_name=doc_name,
            formatting_applied=len(formatting_errors) == 0,
            formatting_errors=formatting_errors,
            verification_passed=verification_passed,
        )

    def _generate_doc_name(self, cv_content: CVContentOutput) -> str:
        today = datetime.now().strftime("%Y-%m-%d")
        return f"CV - {cv_content.name} - {today}"

    def _generate_plain_text(self, cv_content: CVContentOutput) -> str:
        """Generate plain text CV content."""
        lines = []

        # Name
        lines.append(cv_content.name)
        lines.append("")

        # Contact
        contact_parts = []
        if cv_content.contact.email:
            contact_parts.append(cv_content.contact.email)
        if cv_content.contact.phone:
            contact_parts.append(cv_content.contact.phone)
        if cv_content.contact.linkedin:
            contact_parts.append(cv_content.contact.linkedin)
        lines.append(" | ".join(contact_parts))
        lines.append("")

        # Summary
        lines.append("Summary")
        lines.append(cv_content.summary)
        lines.append("")

        # Experience
        lines.append("Experience")
        for exp in cv_content.experience:
            lines.append(f"{exp.title}")
            lines.append(f"{exp.company}")
            lines.append(f"{exp.start_date} - {exp.end_date or 'Present'}")
            for achievement in exp.achievements:
                lines.append(f"• {achievement}")
            lines.append("")

        # ... similar for education, skills, etc.

        return "\n".join(lines)

    async def _apply_formatting(self, doc_id: str, cv_content: CVContentOutput):
        """Apply formatting to the document."""
        # Format name as title
        await self.drive.format_paragraph(
            doc_id,
            text_to_find=cv_content.name,
            named_style_type="TITLE",
            alignment="CENTER",
        )

        # Format section headers
        for section in ["Summary", "Experience", "Education", "Skills", "Awards", "Additional"]:
            try:
                await self.drive.format_paragraph(
                    doc_id,
                    text_to_find=section,
                    named_style_type="HEADING_1",
                )
            except:
                pass  # Section may not exist

        # Format job titles as bold
        for exp in cv_content.experience:
            await self.drive.format_text(
                doc_id,
                text_to_find=exp.title,
                bold=True,
            )
            await self.drive.format_text(
                doc_id,
                text_to_find=exp.company,
                bold=True,
            )

    async def _verify_formatting(self, doc_id: str) -> bool:
        """Verify formatting was applied correctly."""
        try:
            content = await self.drive.get_doc_content(doc_id, include_formatting=True)
            # Check for expected formatting markers
            return "style=bold" in content or "TITLE" in content
        except:
            return False
```

### 6.2 No Prompt Needed

This agent uses MCP tools for formatting, no LLM.

---

## 7. Error Handling Strategy

### 7.1 Per-Agent Error Types

```python
class CVBuilderError(Exception):
    """Base exception for CV Builder."""
    pass

class ConfigError(CVBuilderError):
    """Configuration errors."""
    pass

class MaterialsError(CVBuilderError):
    """Google Drive access errors."""
    pass

class JobAnalysisError(CVBuilderError):
    """Job parsing errors."""
    pass

class GenerationError(CVBuilderError):
    """CV generation errors."""
    pass

class FormattingError(CVBuilderError):
    """Document formatting errors."""
    pass
```

### 7.2 Graceful Degradation

- **MaterialsGatherer**: Continue if some files fail, report errors
- **JobAnalyzer**: Fall back to generic analysis if URL fails
- **CVGenerator**: Generate even if some sections are sparse
- **DocFormatter**: Create doc even if some formatting fails

---

## 8. Testing Strategy

### 8.1 Unit Tests

Each agent should have:
- Happy path test
- Error handling test
- Edge case tests

### 8.2 Integration Tests

- Full pipeline with mock Google Drive
- Full pipeline with real job URL

### 8.3 Test Fixtures

Create sample materials and job descriptions for testing:
- `tests/fixtures/sample_cv_materials.json`
- `tests/fixtures/sample_job_posting.txt`
- `tests/fixtures/expected_cv_output.json`
