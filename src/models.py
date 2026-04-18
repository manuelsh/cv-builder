"""Pydantic models for CV Builder agents."""

from typing import Any
from pydantic import BaseModel, Field


# ============================================================================
# ConfigReader Output
# ============================================================================

class ConfigOutput(BaseModel):
    """Output from ConfigReaderAgent."""

    source_folders: list[str] = Field(description="Google Drive folder IDs")
    output_folder: str | None = Field(default=None, description="Output folder ID")
    max_pages: int = Field(default=2, ge=1, le=3)
    language: str = Field(default="en")
    style: str = Field(default="modern")
    template: str = Field(default="chronological")
    include_photo: bool = Field(default=False)
    contact_info: list[str] = Field(default_factory=lambda: ["email", "phone", "linkedin"])
    other_instructions: str | None = Field(default=None)


# ============================================================================
# MaterialsGatherer Output
# ============================================================================

class DocumentContent(BaseModel):
    """Content extracted from a single document."""

    source_folder: str
    file_name: str
    file_type: str  # google_doc, pdf, text
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class MaterialsOutput(BaseModel):
    """Output from MaterialsGathererAgent."""

    documents: list[DocumentContent] = Field(default_factory=list)
    total_documents: int = 0
    extraction_errors: list[str] = Field(default_factory=list)


# ============================================================================
# JobAnalyzer Output
# ============================================================================

class JobAnalysisOutput(BaseModel):
    """Output from JobAnalyzerAgent."""

    job_title: str
    company_name: str | None = None
    location: str | None = None
    job_type: str | None = None

    required_skills: list[str] = Field(default_factory=list)
    nice_to_have_skills: list[str] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    qualifications: list[str] = Field(default_factory=list)

    company_culture: str | None = None
    industry: str | None = None
    salary_range: str | None = None

    raw_description: str = ""
    source_type: str = "description"  # url, file, description


# ============================================================================
# CVGenerator Output
# ============================================================================

class ContactInfo(BaseModel):
    """Contact information for CV."""

    email: str | None = None
    phone: str | None = None
    linkedin: str | None = None
    github: str | None = None
    website: str | None = None
    address: str | None = None


class ExperienceEntry(BaseModel):
    """Single work experience entry."""

    title: str
    company: str
    location: str | None = None
    start_date: str
    end_date: str | None = None  # None = Present
    achievements: list[str] = Field(default_factory=list)


class EducationEntry(BaseModel):
    """Single education entry."""

    degree: str
    institution: str
    year: str
    details: str | None = None


class SkillsSection(BaseModel):
    """Skills organized by category."""

    categories: dict[str, list[str]] = Field(default_factory=dict)


class CVContentOutput(BaseModel):
    """Output from CVGeneratorAgent."""

    name: str
    contact: ContactInfo = Field(default_factory=ContactInfo)
    summary: str = ""
    experience: list[ExperienceEntry] = Field(default_factory=list)
    education: list[EducationEntry] = Field(default_factory=list)
    skills: SkillsSection = Field(default_factory=SkillsSection)
    awards: list[str] | None = None
    additional: list[str] | None = None

    style_applied: str = ""
    template_applied: str = ""
    language: str = ""
    estimated_pages: int = 1


# ============================================================================
# DocFormatter Output
# ============================================================================

class DocFormatterOutput(BaseModel):
    """Output from DocFormatterAgent."""

    document_id: str
    document_url: str
    document_name: str
    formatting_applied: bool = False
    formatting_errors: list[str] = Field(default_factory=list)
    verification_passed: bool = False
