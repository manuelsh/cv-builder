"""Pytest configuration and fixtures."""

import json
from pathlib import Path

import pytest

from src.models import (
    ConfigOutput,
    MaterialsOutput,
    DocumentContent,
    JobAnalysisOutput,
    CVContentOutput,
    ContactInfo,
    ExperienceEntry,
    EducationEntry,
    SkillsSection,
)


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_config_path() -> Path:
    """Path to sample config file."""
    return FIXTURES_DIR / "sample_config.yaml"


@pytest.fixture
def sample_job_posting_path() -> Path:
    """Path to sample job posting file."""
    return FIXTURES_DIR / "sample_job_posting.txt"


@pytest.fixture
def sample_job_posting_text() -> str:
    """Sample job posting text content."""
    path = FIXTURES_DIR / "sample_job_posting.txt"
    return path.read_text(encoding="utf-8")


@pytest.fixture
def google_careers_html() -> str:
    """Fixture derived from a Google Careers posting page shape."""
    path = FIXTURES_DIR / "google_careers_job_posting.html"
    return path.read_text(encoding="utf-8")


@pytest.fixture
def sample_config() -> ConfigOutput:
    """Sample configuration output."""
    return ConfigOutput(
        source_folders=["folder_id_1", "folder_id_2"],
        output_folder="output_folder_id",
        max_pages=2,
        language="en",
        style="modern",
        template="chronological",
        include_photo=False,
        contact_info=["email", "phone", "linkedin"],
        other_instructions="Always highlight Python experience\nKeep summary under 3 sentences",
    )


@pytest.fixture
def sample_materials() -> MaterialsOutput:
    """Sample materials output."""
    path = FIXTURES_DIR / "sample_cv_materials.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return MaterialsOutput(
        documents=[DocumentContent(**doc) for doc in data["documents"]],
        total_documents=data["total_documents"],
        extraction_errors=data["extraction_errors"],
    )


@pytest.fixture
def sample_job_analysis() -> JobAnalysisOutput:
    """Sample job analysis output."""
    return JobAnalysisOutput(
        job_title="Senior Machine Learning Engineer",
        company_name="TechCorp AI",
        location="Barcelona, Spain (Hybrid)",
        job_type="Full-time",
        required_skills=[
            "Python",
            "PyTorch",
            "TensorFlow",
            "MLOps",
            "AWS/GCP/Azure",
            "5+ years ML experience",
        ],
        nice_to_have_skills=[
            "PhD",
            "LLMs and GenAI",
            "Kubernetes",
            "Team leadership",
        ],
        responsibilities=[
            "Design and implement ML models for production",
            "Build and maintain ML pipelines",
            "Collaborate with product teams",
            "Mentor junior engineers",
        ],
        qualifications=[
            "MSc or PhD in Computer Science",
            "Track record of deploying ML models",
        ],
        company_culture="Tech-focused, collaborative",
        industry="AI/Technology",
        salary_range="€80,000 - €120,000 + equity",
        raw_description="...",
        source_type="file",
    )


@pytest.fixture
def sample_cv_content() -> CVContentOutput:
    """Sample CV content output."""
    return CVContentOutput(
        name="John Doe",
        contact=ContactInfo(
            email="john.doe@email.com",
            phone="+34 612 345 678",
            linkedin="linkedin.com/in/johndoe",
        ),
        summary="Experienced ML Engineer with 8+ years building production ML systems. Led teams delivering recommendation systems serving 1M+ users.",
        experience=[
            ExperienceEntry(
                title="Senior ML Engineer",
                company="TechCorp",
                location="Barcelona",
                start_date="Jan 2020",
                end_date=None,
                achievements=[
                    "Led team of 5 engineers building recommendation systems",
                    "Reduced model inference latency by 40%",
                    "Deployed 10+ models to production serving 1M+ users",
                ],
            ),
            ExperienceEntry(
                title="ML Engineer",
                company="DataCo",
                location="Madrid",
                start_date="Mar 2016",
                end_date="Dec 2019",
                achievements=[
                    "Built NLP models for text classification",
                    "Implemented MLOps pipelines using Kubernetes",
                    "Trained 20+ engineers on ML best practices",
                ],
            ),
        ],
        education=[
            EducationEntry(
                degree="MSc Computer Science",
                institution="Universitat Politècnica de Catalunya",
                year="2016",
                details=None,
            ),
        ],
        skills=SkillsSection(
            categories={
                "Technical": ["Python", "PyTorch", "TensorFlow", "AWS", "Kubernetes"],
                "Leadership": ["Team management", "Mentoring", "Agile"],
            }
        ),
        awards=None,
        additional=["Languages: Spanish (native), English (fluent)"],
        style_applied="modern",
        template_applied="chronological",
        language="en",
        estimated_pages=2,
    )
