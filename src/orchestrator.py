"""Pipeline orchestrator for CV generation."""

from typing import Any

from src.agents import (
    ConfigReaderAgent,
    MaterialsGathererAgent,
    JobAnalyzerAgent,
    CVGeneratorAgent,
    DocFormatterAgent,
)
from src.models import (
    ConfigOutput,
    CVContentOutput,
    DocFormatterOutput,
)


class PipelineOrchestrator:
    """Coordinates the multi-agent pipeline for CV generation."""

    def __init__(
        self,
        google_drive_caller: Any | None = None,
        llm_config: dict[str, Any] | None = None,
    ):
        """Initialize the orchestrator.

        Args:
            google_drive_caller: Optional MCP caller for Google Drive tools.
            llm_config: Optional runtime LLM configuration overrides.
        """
        self.google_drive_caller = google_drive_caller
        self.llm_config = llm_config or {}

    async def generate_cv(
        self,
        job_target: str,
        config_path: str = "config.yaml",
        dry_run: bool = False,
        style_override: str | None = None,
        language_override: str | None = None,
        max_pages_override: int | None = None,
    ) -> CVContentOutput | DocFormatterOutput:
        """Generate a CV for a job target.

        Args:
            job_target: Job URL, file path, or description.
            config_path: Path to config.yaml.
            dry_run: If True, return CV content without creating Google Doc.
            style_override: Override config style.
            language_override: Override config language.
            max_pages_override: Override config max_pages.

        Returns:
            CVContentOutput if dry_run, otherwise DocFormatterOutput.
        """
        print(f"\n{'='*60}")
        print("CV Builder - Generating CV")
        print(f"{'='*60}\n")

        # Phase 1: Read configuration
        print("[1/5] Reading configuration...")
        config_reader = ConfigReaderAgent(config=self.llm_config)
        config = config_reader.run(config_path)
        print(f"      Style: {config.style}, Template: {config.template}, Pages: {config.max_pages}")

        # Apply overrides
        if style_override:
            config = ConfigOutput(
                **{**config.model_dump(), "style": style_override}
            )
        if language_override:
            config = ConfigOutput(
                **{**config.model_dump(), "language": language_override}
            )
        if max_pages_override:
            config = ConfigOutput(
                **{**config.model_dump(), "max_pages": max_pages_override}
            )

        # Phase 2: Gather materials
        print("[2/5] Gathering materials from Google Drive...")
        materials_gatherer = MaterialsGathererAgent(config=self.llm_config)
        materials = await materials_gatherer.run(config)
        print(f"      Found {materials.total_documents} documents")
        if materials.extraction_errors:
            print(f"      Warnings: {len(materials.extraction_errors)} errors")

        # Phase 3: Analyze job
        print("[3/5] Analyzing job target...")
        job_analyzer = JobAnalyzerAgent(config=self.llm_config)
        job_analysis = await job_analyzer.run(job_target)
        print(f"      Job: {job_analysis.job_title}")
        print(f"      Company: {job_analysis.company_name or 'Not specified'}")
        print(f"      Required skills: {len(job_analysis.required_skills)}")

        # Phase 4: Generate CV
        print("[4/5] Generating CV content...")
        cv_generator = CVGeneratorAgent(config=self.llm_config)
        cv_content = await cv_generator.run(
            config=config,
            materials=materials,
            job_analysis=job_analysis,
        )
        print(f"      Name: {cv_content.name}")
        print(f"      Experience entries: {len(cv_content.experience)}")
        print(f"      Estimated pages: {cv_content.estimated_pages}")

        # Phase 5: Create Google Doc (unless dry run)
        if dry_run:
            print("[5/5] Dry run - skipping Google Doc creation")
            print(f"\n{'='*60}")
            print("Generation Complete (Dry Run)")
            print(f"{'='*60}")
            return cv_content

        print("[5/5] Creating and formatting Google Doc...")
        doc_formatter = DocFormatterAgent(config=self.llm_config)
        result = await doc_formatter.run(config=config, cv_content=cv_content)
        print(f"      Document created: {result.document_name}")
        print(f"      Formatting applied: {result.formatting_applied}")

        print(f"\n{'='*60}")
        print("Generation Complete!")
        print(f"{'='*60}")
        print(f"Document URL: {result.document_url}")

        return result
