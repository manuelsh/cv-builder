"""DocFormatterAgent - creates and formats Google Doc from CV content."""

from datetime import datetime
from typing import Any

from src.agents.base import BaseAgent
from src.google_drive.client import GoogleDriveClient
from src.models import ConfigOutput, CVContentOutput, DocFormatterOutput


class DocFormatterAgent(BaseAgent):
    """Agent that creates and formats Google Docs from CV content."""

    agent_name = "doc_formatter"

    def __init__(
        self,
        google_drive_client: GoogleDriveClient | None = None,
        **kwargs: Any,
    ):
        """Initialize the agent.

        Args:
            google_drive_client: Google Drive client. Creates one if not provided.
            **kwargs: Additional arguments for BaseAgent.
        """
        super().__init__(**kwargs)
        self.drive = google_drive_client or GoogleDriveClient()

    async def run(
        self,
        config: ConfigOutput,
        cv_content: CVContentOutput,
    ) -> DocFormatterOutput:
        """Create and format Google Doc.

        Args:
            config: Configuration with output folder.
            cv_content: Generated CV content.

        Returns:
            DocFormatterOutput with document info.
        """
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
        formatting_errors: list[str] = []
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
        """Generate document name.

        Args:
            cv_content: CV content with name.

        Returns:
            Document name string.
        """
        today = datetime.now().strftime("%Y-%m-%d")
        return f"CV - {cv_content.name} - {today}"

    def _generate_plain_text(self, cv_content: CVContentOutput) -> str:
        """Generate plain text CV content.

        Args:
            cv_content: Structured CV content.

        Returns:
            Plain text formatted CV.
        """
        lines: list[str] = []

        # Name
        lines.append(cv_content.name)
        lines.append("")

        # Contact
        contact_parts: list[str] = []
        if cv_content.contact.email:
            contact_parts.append(cv_content.contact.email)
        if cv_content.contact.phone:
            contact_parts.append(cv_content.contact.phone)
        if cv_content.contact.linkedin:
            contact_parts.append(cv_content.contact.linkedin)
        if cv_content.contact.github:
            contact_parts.append(cv_content.contact.github)
        if cv_content.contact.website:
            contact_parts.append(cv_content.contact.website)

        if contact_parts:
            lines.append(" | ".join(contact_parts))
            lines.append("")

        # Summary
        if cv_content.summary:
            lines.append("Summary")
            lines.append(cv_content.summary)
            lines.append("")

        # Experience
        if cv_content.experience:
            lines.append("Experience")
            lines.append("")
            for exp in cv_content.experience:
                lines.append(exp.title)
                company_line = exp.company
                if exp.location:
                    company_line += f", {exp.location}"
                lines.append(company_line)
                end_date = exp.end_date or "Present"
                lines.append(f"{exp.start_date} - {end_date}")
                for achievement in exp.achievements:
                    lines.append(f"• {achievement}")
                lines.append("")

        # Education
        if cv_content.education:
            lines.append("Education")
            lines.append("")
            for edu in cv_content.education:
                lines.append(f"{edu.degree} - {edu.institution} ({edu.year})")
                if edu.details:
                    lines.append(edu.details)
                lines.append("")

        # Skills
        if cv_content.skills and cv_content.skills.categories:
            lines.append("Skills")
            lines.append("")
            for category, skills in cv_content.skills.categories.items():
                lines.append(f"{category}: {', '.join(skills)}")
            lines.append("")

        # Awards
        if cv_content.awards:
            lines.append("Awards")
            lines.append("")
            for award in cv_content.awards:
                lines.append(f"• {award}")
            lines.append("")

        # Additional
        if cv_content.additional:
            lines.append("Additional")
            lines.append("")
            for item in cv_content.additional:
                lines.append(f"• {item}")
            lines.append("")

        return "\n".join(lines)

    async def _apply_formatting(
        self,
        doc_id: str,
        cv_content: CVContentOutput,
    ) -> None:
        """Apply formatting to the document.

        Args:
            doc_id: Google Doc ID.
            cv_content: CV content for reference.
        """
        # Format name as title
        await self.drive.format_paragraph(
            doc_id,
            text_to_find=cv_content.name,
            named_style_type="TITLE",
            alignment="CENTER",
        )

        # Format section headers
        sections = ["Summary", "Experience", "Education", "Skills", "Awards", "Additional"]
        for section in sections:
            try:
                await self.drive.format_paragraph(
                    doc_id,
                    text_to_find=section,
                    named_style_type="HEADING_1",
                )
            except Exception:
                pass  # Section may not exist

        # Format job titles as bold
        for exp in cv_content.experience:
            try:
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
            except Exception:
                pass

        # Format education entries
        for edu in cv_content.education:
            try:
                await self.drive.format_text(
                    doc_id,
                    text_to_find=edu.degree,
                    bold=True,
                )
            except Exception:
                pass

        # Format skill categories
        if cv_content.skills and cv_content.skills.categories:
            for category in cv_content.skills.categories:
                try:
                    await self.drive.format_text(
                        doc_id,
                        text_to_find=f"{category}:",
                        bold=True,
                    )
                except Exception:
                    pass

    async def _verify_formatting(self, doc_id: str) -> bool:
        """Verify formatting was applied correctly.

        Args:
            doc_id: Google Doc ID.

        Returns:
            True if formatting markers found.
        """
        try:
            content = await self.drive.get_doc_content(doc_id, include_formatting=True)
            # Check for formatting markers
            return "style=bold" in content or "TITLE" in content or "HEADING" in content
        except Exception:
            return False
