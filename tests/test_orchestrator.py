"""Tests for PipelineOrchestrator."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.orchestrator import PipelineOrchestrator
from src.models import (
    ConfigOutput,
    MaterialsOutput,
    JobAnalysisOutput,
    CVContentOutput,
    DocFormatterOutput,
)


class TestPipelineOrchestrator:
    """Tests for PipelineOrchestrator."""

    @pytest.fixture
    def mock_agents(self, sample_config, sample_materials, sample_job_analysis, sample_cv_content):
        """Create mock agents."""
        config_reader = MagicMock()
        config_reader.run = MagicMock(return_value=sample_config)

        materials_gatherer = MagicMock()
        materials_gatherer.run = AsyncMock(return_value=sample_materials)

        job_analyzer = MagicMock()
        job_analyzer.run = AsyncMock(return_value=sample_job_analysis)

        cv_generator = MagicMock()
        cv_generator.run = AsyncMock(return_value=sample_cv_content)

        doc_formatter = MagicMock()
        doc_formatter.run = AsyncMock(return_value=DocFormatterOutput(
            document_id="doc_123",
            document_url="https://docs.google.com/document/d/doc_123/edit",
            document_name="CV - John Doe - 2026-03-17",
            formatting_applied=True,
            verification_passed=True,
        ))

        return {
            "config_reader": config_reader,
            "materials_gatherer": materials_gatherer,
            "job_analyzer": job_analyzer,
            "cv_generator": cv_generator,
            "doc_formatter": doc_formatter,
        }

    @pytest.mark.asyncio
    async def test_full_pipeline(self, mock_agents):
        """Test running the full pipeline."""
        with patch("src.orchestrator.ConfigReaderAgent", return_value=mock_agents["config_reader"]), \
             patch("src.orchestrator.MaterialsGathererAgent", return_value=mock_agents["materials_gatherer"]), \
             patch("src.orchestrator.JobAnalyzerAgent", return_value=mock_agents["job_analyzer"]), \
             patch("src.orchestrator.CVGeneratorAgent", return_value=mock_agents["cv_generator"]), \
             patch("src.orchestrator.DocFormatterAgent", return_value=mock_agents["doc_formatter"]):

            orchestrator = PipelineOrchestrator()
            result = await orchestrator.generate_cv(
                job_target="Senior ML Engineer role",
                config_path="config.yaml",
            )

            assert result.document_id == "doc_123"
            assert "docs.google.com" in result.document_url

    @pytest.mark.asyncio
    async def test_pipeline_calls_agents_in_order(self, mock_agents, sample_config, sample_materials, sample_job_analysis, sample_cv_content):
        """Test that agents are called in correct order."""
        call_order = []

        # Set up tracking side effects while preserving return values
        def make_sync_tracker(name, return_value):
            def tracker(*args, **kwargs):
                call_order.append(name)
                return return_value
            return tracker

        def make_async_tracker(name, return_value):
            async def tracker(*args, **kwargs):
                call_order.append(name)
                return return_value
            return tracker

        # config_reader is sync
        mock_agents["config_reader"].run = MagicMock(
            side_effect=make_sync_tracker("config_reader", sample_config)
        )

        # All others are async
        mock_agents["materials_gatherer"].run = AsyncMock(
            side_effect=make_async_tracker("materials_gatherer", sample_materials)
        )
        mock_agents["job_analyzer"].run = AsyncMock(
            side_effect=make_async_tracker("job_analyzer", sample_job_analysis)
        )
        mock_agents["cv_generator"].run = AsyncMock(
            side_effect=make_async_tracker("cv_generator", sample_cv_content)
        )
        mock_agents["doc_formatter"].run = AsyncMock(
            side_effect=make_async_tracker("doc_formatter", DocFormatterOutput(
                document_id="doc_123",
                document_url="https://docs.google.com/document/d/doc_123/edit",
                document_name="CV - John Doe - 2026-03-17",
                formatting_applied=True,
                verification_passed=True,
            ))
        )

        with patch("src.orchestrator.ConfigReaderAgent", return_value=mock_agents["config_reader"]), \
             patch("src.orchestrator.MaterialsGathererAgent", return_value=mock_agents["materials_gatherer"]), \
             patch("src.orchestrator.JobAnalyzerAgent", return_value=mock_agents["job_analyzer"]), \
             patch("src.orchestrator.CVGeneratorAgent", return_value=mock_agents["cv_generator"]), \
             patch("src.orchestrator.DocFormatterAgent", return_value=mock_agents["doc_formatter"]):

            orchestrator = PipelineOrchestrator()
            await orchestrator.generate_cv(
                job_target="Test job",
                config_path="config.yaml",
            )

        expected_order = [
            "config_reader",
            "materials_gatherer",
            "job_analyzer",
            "cv_generator",
            "doc_formatter",
        ]
        assert call_order == expected_order

    @pytest.mark.asyncio
    async def test_dry_run_skips_doc_formatter(self, mock_agents, sample_cv_content):
        """Test that dry run doesn't create Google Doc."""
        with patch("src.orchestrator.ConfigReaderAgent", return_value=mock_agents["config_reader"]), \
             patch("src.orchestrator.MaterialsGathererAgent", return_value=mock_agents["materials_gatherer"]), \
             patch("src.orchestrator.JobAnalyzerAgent", return_value=mock_agents["job_analyzer"]), \
             patch("src.orchestrator.CVGeneratorAgent", return_value=mock_agents["cv_generator"]), \
             patch("src.orchestrator.DocFormatterAgent", return_value=mock_agents["doc_formatter"]):

            orchestrator = PipelineOrchestrator()
            result = await orchestrator.generate_cv(
                job_target="Test job",
                config_path="config.yaml",
                dry_run=True,
            )

            # Should return CV content, not doc formatter output
            assert isinstance(result, CVContentOutput)
            # Doc formatter should not be called
            mock_agents["doc_formatter"].run.assert_not_called()

    @pytest.mark.asyncio
    async def test_config_override_style(self, mock_agents, sample_config):
        """Test that style override is applied."""
        with patch("src.orchestrator.ConfigReaderAgent", return_value=mock_agents["config_reader"]), \
             patch("src.orchestrator.MaterialsGathererAgent", return_value=mock_agents["materials_gatherer"]), \
             patch("src.orchestrator.JobAnalyzerAgent", return_value=mock_agents["job_analyzer"]), \
             patch("src.orchestrator.CVGeneratorAgent", return_value=mock_agents["cv_generator"]), \
             patch("src.orchestrator.DocFormatterAgent", return_value=mock_agents["doc_formatter"]):

            orchestrator = PipelineOrchestrator()
            await orchestrator.generate_cv(
                job_target="Test job",
                config_path="config.yaml",
                style_override="technical",
            )

            # Check that CV generator received updated config
            cv_gen_call = mock_agents["cv_generator"].run.call_args
            config_arg = cv_gen_call[1]["config"]
            assert config_arg.style == "technical"

    @pytest.mark.asyncio
    async def test_handles_config_error(self, mock_agents):
        """Test handling of config reader error."""
        mock_agents["config_reader"].run.side_effect = ValueError("Invalid config")

        with patch("src.orchestrator.ConfigReaderAgent", return_value=mock_agents["config_reader"]):
            orchestrator = PipelineOrchestrator()

            with pytest.raises(ValueError, match="Invalid config"):
                await orchestrator.generate_cv(
                    job_target="Test job",
                    config_path="config.yaml",
                )

    @pytest.mark.asyncio
    async def test_handles_materials_error(self, mock_agents):
        """Test handling of materials gatherer error."""
        mock_agents["materials_gatherer"].run.side_effect = Exception("Drive error")

        with patch("src.orchestrator.ConfigReaderAgent", return_value=mock_agents["config_reader"]), \
             patch("src.orchestrator.MaterialsGathererAgent", return_value=mock_agents["materials_gatherer"]):

            orchestrator = PipelineOrchestrator()

            with pytest.raises(Exception, match="Drive error"):
                await orchestrator.generate_cv(
                    job_target="Test job",
                    config_path="config.yaml",
                )


class TestPipelineOrchestratorIntegration:
    """Integration tests for PipelineOrchestrator."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_real_pipeline(self, sample_job_posting_path):
        """Test full pipeline with real services."""
        orchestrator = PipelineOrchestrator()
        result = await orchestrator.generate_cv(
            job_target=str(sample_job_posting_path),
            config_path="config.yaml",
        )

        assert result.document_id is not None
