**Status:** Draft
**Created:** 2026-03-17
**Purpose:** Define the multi-agent architecture for generating personalized CVs from Google Drive materials and job targets.

---

# Specification 1: CV Builder Agents Architecture

## 1. Executive Summary

**1.1 Objective**: Build a multi-agent system that generates tailored CVs by reading user materials from Google Drive, analyzing job targets, and outputting professionally formatted Google Docs.

**1.2 Current State**: Manual CV generation via Claude Code skill (`/cv`) that reads config, fetches materials, analyzes jobs, and creates formatted Google Docs in a single conversation.

**1.3 Solution**: Create a pipeline of 5 specialized agents:
1. **ConfigReader** - Reads and validates config.yaml
2. **MaterialsGatherer** - Fetches and parses user materials from Google Drive
3. **JobAnalyzer** - Parses job target (URL, file, or description)
4. **CVGenerator** - Generates tailored CV content
5. **DocFormatter** - Creates and formats Google Doc output

**1.4 Key Benefits**:
- Modular, testable components
- CLI interface for easy use
- Reusable agents for different workflows
- Better error handling per stage
- Cost tracking per agent

---

## 2. Architecture Overview

### 2.1 Pipeline Flow

```
┌─────────────────────┐
│    ConfigReader     │ ──> Reads config.yaml, validates settings
└─────────────────────┘
           │
           v
┌─────────────────────┐
│  MaterialsGatherer  │ ──> Fetches Google Drive docs, extracts text
└─────────────────────┘
           │
           v
┌─────────────────────┐
│    JobAnalyzer      │ ──> Parses job target (URL/file/description)
└─────────────────────┘
           │
           v
┌─────────────────────┐
│    CVGenerator      │ ──> Generates tailored CV content (LLM)
└─────────────────────┘
           │
           v
┌─────────────────────┐
│    DocFormatter     │ ──> Creates & formats Google Doc
└─────────────────────┘
```

### 2.2 Data Flow

```
config.yaml ──> ConfigOutput
                     │
                     v
Google Drive ──> MaterialsOutput (user background, experience, skills)
                     │
                     v
Job Target ────> JobAnalysisOutput (requirements, skills, company info)
                     │
                     v
                CVContentOutput (structured CV sections)
                     │
                     v
                GoogleDocOutput (doc ID, URL, formatting status)
```

---

## 3. Agent Specifications

### 3.1 ConfigReaderAgent

**Responsibility:** Read and validate configuration from config.yaml

**Tasks:**
- Read `config.yaml` from project root
- Validate required fields (source_folders)
- Apply defaults for optional fields
- Return structured config object

**Input:** None (reads from filesystem)

**Output:** `ConfigOutput`
```python
class ConfigOutput(BaseModel):
    source_folders: list[str]  # Google Drive folder IDs
    output_folder: str | None
    max_pages: int  # 1, 2, or 3
    language: str   # en, es, de, fr, etc.
    style: str      # formal, modern, creative, technical
    template: str   # chronological, functional, combination
    include_photo: bool
    contact_info: list[str]  # email, phone, linkedin, github, etc.
    other_instructions: str | None
```

**Model:** None (no LLM needed)

---

### 3.2 MaterialsGathererAgent

**Responsibility:** Fetch user materials from Google Drive and extract content

**Tasks:**
- Connect to Google Drive via MCP tools
- List files in each source folder
- Read Google Docs content (markdown format)
- Download and parse PDFs
- Aggregate all user materials

**Input:** `ConfigOutput`

**Output:** `MaterialsOutput`
```python
class MaterialsOutput(BaseModel):
    documents: list[DocumentContent]
    total_documents: int
    extraction_errors: list[str]

class DocumentContent(BaseModel):
    source_folder: str
    file_name: str
    file_type: str  # google_doc, pdf, text
    content: str
    metadata: dict[str, Any]  # creation date, last modified, etc.
```

**MCP Tools Used:**
- `mcp__google-drive__listFolder`
- `mcp__google-drive__readGoogleDoc`
- `mcp__google-drive__downloadFile`

**Model:** None (no LLM needed, just data extraction)

---

### 3.3 JobAnalyzerAgent

**Responsibility:** Parse and analyze job target to extract requirements

**Tasks:**
- Detect input type (URL, file path, or description)
- For URLs: Fetch and parse web content
- For files: Read local file
- For descriptions: Use directly
- Extract structured job information using LLM

**Input:** `job_target: str` (URL, path, or description)

**Output:** `JobAnalysisOutput`
```python
class JobAnalysisOutput(BaseModel):
    job_title: str
    company_name: str | None
    location: str | None
    job_type: str | None  # full-time, contract, etc.

    required_skills: list[str]
    nice_to_have_skills: list[str]
    responsibilities: list[str]
    qualifications: list[str]

    company_culture: str | None
    industry: str | None
    salary_range: str | None

    raw_description: str
    source_type: str  # url, file, description
```

**Model:** `fast` (extraction task)

---

### 3.4 CVGeneratorAgent

**Responsibility:** Generate tailored CV content based on materials and job analysis

**Tasks:**
- Analyze user materials to extract experience, skills, achievements
- Match user profile to job requirements
- Generate CV sections following config style/template
- Apply language setting
- Respect max_pages constraint
- Follow other_instructions

**Input:**
- `ConfigOutput`
- `MaterialsOutput`
- `JobAnalysisOutput`

**Output:** `CVContentOutput`
```python
class CVContentOutput(BaseModel):
    name: str
    contact: ContactInfo
    summary: str
    experience: list[ExperienceEntry]
    education: list[EducationEntry]
    skills: SkillsSection
    awards: list[str] | None
    additional: list[str] | None

    style_applied: str
    template_applied: str
    language: str
    estimated_pages: int

class ContactInfo(BaseModel):
    email: str | None
    phone: str | None
    linkedin: str | None
    github: str | None
    website: str | None
    address: str | None

class ExperienceEntry(BaseModel):
    title: str
    company: str
    location: str | None
    start_date: str
    end_date: str | None  # None = Present
    achievements: list[str]

class EducationEntry(BaseModel):
    degree: str
    institution: str
    year: str
    details: str | None

class SkillsSection(BaseModel):
    categories: dict[str, list[str]]  # e.g., {"Technical": ["Python", ...]}
```

**Model:** `best` (critical content generation)

---

### 3.5 DocFormatterAgent

**Responsibility:** Create formatted Google Doc from CV content

**Tasks:**
- Create new Google Doc in output folder
- Insert CV content with proper structure
- Apply formatting (headings, bold, alignment)
- Verify formatting was applied
- Return document link

**Input:**
- `ConfigOutput`
- `CVContentOutput`

**Output:** `DocFormatterOutput`
```python
class DocFormatterOutput(BaseModel):
    document_id: str
    document_url: str
    document_name: str
    formatting_applied: bool
    formatting_errors: list[str]
    verification_passed: bool
```

**MCP Tools Used:**
- `mcp__google-drive__createGoogleDoc`
- `mcp__google-drive__formatGoogleDocParagraph`
- `mcp__google-drive__formatGoogleDocText`
- `mcp__google-drive__getGoogleDocContent`

**Model:** None (formatting only, no LLM needed)

---

## 4. Project Structure

```
cv-builder/
├── .specs/                      # Specification files
│   └── 1-cv-builder-agents-architecture.md
├── config.yaml                  # User configuration
├── pyproject.toml              # Project dependencies
├── README.md                   # Documentation
├── CLAUDE.md                   # Claude Code instructions
├── .env.example                # Environment template
├── .env                        # Local environment (gitignored)
├── src/
│   ├── __init__.py
│   ├── cli.py                  # CLI entry point
│   ├── orchestrator.py         # Pipeline orchestrator
│   ├── models.py               # Pydantic data models
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base.py             # BaseAgent class
│   │   ├── config_reader.py
│   │   ├── materials_gatherer.py
│   │   ├── job_analyzer.py
│   │   ├── cv_generator.py
│   │   └── doc_formatter.py
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── client.py           # LLM client (litellm)
│   │   └── config.py           # Model configuration
│   ├── google_drive/
│   │   ├── __init__.py
│   │   └── client.py           # Google Drive MCP wrapper
│   └── utils/
│       ├── __init__.py
│       ├── web_fetcher.py      # URL content fetching
│       └── output_manager.py   # Output logging
├── prompts/
│   ├── README.md
│   ├── __init__.py
│   ├── loader.py
│   ├── registry.py
│   ├── base/
│   │   ├── cv_style_modern.md
│   │   ├── cv_style_formal.md
│   │   ├── cv_style_creative.md
│   │   └── cv_style_technical.md
│   └── agents/
│       ├── job_analyzer.md
│       └── cv_generator.md
└── tests/
    ├── __init__.py
    ├── test_config_reader.py
    ├── test_materials_gatherer.py
    ├── test_job_analyzer.py
    ├── test_cv_generator.py
    └── test_doc_formatter.py
```

---

## 5. CLI Interface

### 5.1 Commands

```bash
# Generate a CV for a job target
cv-builder generate <job_target>

# Generate with options
cv-builder generate "https://linkedin.com/jobs/..." --output ./my-cv.json --dry-run

# Validate configuration
cv-builder validate

# List available materials
cv-builder materials
```

### 5.2 Command Options (generate)

| Option | Description |
|--------|-------------|
| `job_target` | Job URL, file path, or description (required) |
| `--output`, `-o` | Custom output directory |
| `--dry-run` | Print CV content without creating Google Doc |
| `--style` | Override config style (formal/modern/creative/technical) |
| `--language` | Override config language |
| `--max-pages` | Override config max pages |

### 5.3 Example Usage

```bash
# From LinkedIn URL
cv-builder generate "https://linkedin.com/jobs/view/12345"

# From local job description file
cv-builder generate ./job-description.txt

# From inline description
cv-builder generate "Senior Python Developer at fintech startup"

# With overrides
cv-builder generate "..." --style technical --max-pages 1 --language es
```

---

## 6. Configuration

### 6.1 config.yaml

```yaml
# Google Drive folders with user materials (URLs or IDs)
source_folders:
  - YOUR_FOLDER_ID_1
  - YOUR_FOLDER_ID_2

# Output folder (default: first source folder)
output_folder: "YOUR_OUTPUT_FOLDER_ID"

format:
  max_pages: 2
  language: en
  style: modern
  template: chronological

content:
  include_photo: false
  contact_info:
    - email
    - phone
    - linkedin

other_instructions: |
  Always highlight Python and cloud experience
  Keep summary under 3 sentences
```

### 6.2 .env

```bash
# AWS Bedrock Configuration
AWS_REGION=eu-west-1
BEDROCK_MODEL_FAST=arn:aws:bedrock:...
BEDROCK_MODEL_BEST=arn:aws:bedrock:...

# Google Drive MCP (handled via Claude Code MCP config)
# No additional config needed if using Claude Code
```

---

## 7. Dependencies

```toml
[project]
name = "cv-builder"
version = "0.1.0"
description = "Multi-agent system for generating personalized CVs"
requires-python = ">=3.10"
dependencies = [
    "litellm~=1.67.0",
    "pydantic~=2.10.0",
    "pyyaml~=6.0.2",
    "python-dotenv~=1.0.1",
    "httpx~=0.28.1",
    "boto3~=1.36.0",
]

[project.optional-dependencies]
dev = [
    "pytest~=8.3.0",
    "pytest-asyncio~=0.25.0",
]

[project.scripts]
cv-builder = "src.cli:main"
```

---

## 8. Implementation Plan

### Phase 1: Foundation (1-2 days)
- [ ] Set up project structure
- [ ] Create pyproject.toml and dependencies
- [ ] Implement BaseAgent class
- [ ] Implement LLM client (litellm + Bedrock)
- [ ] Create Pydantic models

### Phase 2: Non-LLM Agents (1 day)
- [ ] ConfigReaderAgent
- [ ] MaterialsGathererAgent (Google Drive integration)
- [ ] DocFormatterAgent (Google Doc creation)

### Phase 3: LLM Agents (1-2 days)
- [ ] JobAnalyzerAgent with prompts
- [ ] CVGeneratorAgent with prompts
- [ ] Style-specific prompts (modern, formal, etc.)

### Phase 4: Orchestration & CLI (1 day)
- [ ] PipelineOrchestrator
- [ ] CLI implementation
- [ ] Output logging

### Phase 5: Testing & Polish (1 day)
- [ ] Unit tests for each agent
- [ ] Integration test with real job posting
- [ ] Documentation

---

## 9. Open Questions

1. **Google Drive MCP Integration**: Should we use MCP tools directly in agents or create a wrapper client?
   - **Decision**: Create a `GoogleDriveClient` wrapper for better testability

2. **PDF Handling**: How to extract text from PDFs?
   - **Decision**: Use Google Drive's PDF-to-Doc conversion via `convertPdfToGoogleDoc` MCP tool

3. **Cost Tracking**: Should we track LLM costs per generation?
   - **Decision**: Yes, similar to theoria-agents, track cost by agent

4. **Caching**: Should we cache user materials?
   - **Decision**: No caching initially, materials may change frequently

---

## 10. Success Criteria

1. ✅ CLI generates CV from job URL in < 2 minutes
2. ✅ CV matches configured style and language
3. ✅ CV fits within max_pages constraint
4. ✅ Google Doc is properly formatted with headings and bold text
5. ✅ Cost per generation is logged
6. ✅ Errors at each stage are handled gracefully
