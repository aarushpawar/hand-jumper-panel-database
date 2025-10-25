"""
Unit tests for pipeline orchestration system.
"""

import pytest
import numpy as np
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from core.pipeline import (
    Pipeline, PipelineBuilder, PipelineStage, PipelineContext,
    StageResult, StageStatus
)
from core.models import Panel, AnalysisResult, Character
from core.analyzer_plugin import AnalyzerPlugin


class MockAnalyzer(AnalyzerPlugin):
    """Mock analyzer for testing."""

    def __init__(self, config=None, should_fail=False):
        super().__init__(config)
        self.should_fail = should_fail
        self.call_count = 0

    @property
    def name(self) -> str:
        return "mock_analyzer"

    @property
    def version(self) -> str:
        return "1.0.0"

    def analyze(self, image: np.ndarray, panel_path: Path) -> AnalysisResult:
        self.call_count += 1
        if self.should_fail:
            raise ValueError("Mock analyzer failure")
        return AnalysisResult(
            characters=[Character("MockChar", 0.9)]
        )


class TestPipelineStage:
    """Test PipelineStage."""

    def test_creation(self):
        analyzer = MockAnalyzer()
        stage = PipelineStage("test_stage", analyzer, dependencies=["dep1"])

        assert stage.name == "test_stage"
        assert stage.analyzer == analyzer
        assert stage.dependencies == ["dep1"]

    def test_can_execute_no_dependencies(self):
        analyzer = MockAnalyzer()
        stage = PipelineStage("test_stage", analyzer, dependencies=[])

        panel = Panel("p1", "ep001", 1, "test.jpg", 800, 1200)
        context = PipelineContext(panel=panel)

        assert stage.can_execute(context) is True

    def test_can_execute_dependencies_not_met(self):
        analyzer = MockAnalyzer()
        stage = PipelineStage("test_stage", analyzer, dependencies=["missing_dep"])

        panel = Panel("p1", "ep001", 1, "test.jpg", 800, 1200)
        context = PipelineContext(panel=panel)

        assert stage.can_execute(context) is False

    def test_can_execute_dependencies_met(self):
        analyzer = MockAnalyzer()
        stage = PipelineStage("test_stage", analyzer, dependencies=["dep1"])

        panel = Panel("p1", "ep001", 1, "test.jpg", 800, 1200)
        context = PipelineContext(panel=panel)

        # Add completed dependency
        context.stage_results.append(
            StageResult("dep1", StageStatus.COMPLETED)
        )

        assert stage.can_execute(context) is True

    def test_execute_success(self):
        analyzer = MockAnalyzer()
        stage = PipelineStage("test_stage", analyzer)

        panel = Panel("p1", "ep001", 1, "test.jpg", 800, 1200)
        image = np.zeros((100, 100, 3), dtype=np.uint8)
        context = PipelineContext(panel=panel, image=image)

        result = stage.execute(context)

        assert result.status == StageStatus.COMPLETED
        assert result.stage_name == "test_stage"
        assert result.error is None
        assert "test_stage" in context.intermediate_results

    def test_execute_failure(self):
        analyzer = MockAnalyzer(should_fail=True)
        stage = PipelineStage("test_stage", analyzer)

        panel = Panel("p1", "ep001", 1, "test.jpg", 800, 1200)
        image = np.zeros((100, 100, 3), dtype=np.uint8)
        context = PipelineContext(panel=panel, image=image)

        result = stage.execute(context)

        assert result.status == StageStatus.FAILED
        assert result.error is not None
        assert "Mock analyzer failure" in result.error


class TestPipeline:
    """Test Pipeline orchestrator."""

    def test_creation(self):
        pipeline = Pipeline()
        assert len(pipeline.stages) == 0
        assert pipeline.continue_on_error is True
        assert pipeline.max_workers == 4

    def test_creation_with_config(self):
        config = {'continue_on_error': False, 'max_workers': 8}
        pipeline = Pipeline(config=config)

        assert pipeline.continue_on_error is False
        assert pipeline.max_workers == 8

    def test_add_stage(self):
        pipeline = Pipeline()
        analyzer = MockAnalyzer()
        pipeline.add_stage("test", analyzer)

        assert len(pipeline.stages) == 1
        assert pipeline.stages[0].name == "test"

    @patch('core.pipeline.Pipeline._load_image')
    def test_process_panel_success(self, mock_load_image):
        # Mock image loading
        mock_load_image.return_value = np.zeros((100, 100, 3), dtype=np.uint8)

        pipeline = Pipeline()
        analyzer = MockAnalyzer()
        pipeline.add_stage("test", analyzer)

        panel = Panel("p1", "ep001", 1, "test.jpg", 800, 1200)
        result = pipeline.process_panel(panel)

        assert result.ai_analysis is not None
        assert len(result.ai_analysis.characters) == 1

    @patch('core.pipeline.Pipeline._load_image')
    def test_process_panel_image_load_failure(self, mock_load_image):
        mock_load_image.return_value = None

        pipeline = Pipeline()
        analyzer = MockAnalyzer()
        pipeline.add_stage("test", analyzer)

        panel = Panel("p1", "ep001", 1, "test.jpg", 800, 1200)
        result = pipeline.process_panel(panel)

        # Should return panel unchanged
        assert result.ai_analysis is None

    @patch('core.pipeline.Pipeline._load_image')
    def test_process_panel_continue_on_error(self, mock_load_image):
        mock_load_image.return_value = np.zeros((100, 100, 3), dtype=np.uint8)

        pipeline = Pipeline(config={'continue_on_error': True})
        failing_analyzer = MockAnalyzer(should_fail=True)
        working_analyzer = MockAnalyzer()

        pipeline.add_stage("failing", failing_analyzer)
        pipeline.add_stage("working", working_analyzer)

        panel = Panel("p1", "ep001", 1, "test.jpg", 800, 1200)
        result = pipeline.process_panel(panel)

        # Both stages should have been attempted
        assert failing_analyzer.call_count == 1
        assert working_analyzer.call_count == 1

    @patch('core.pipeline.Pipeline._load_image')
    def test_process_panel_stop_on_error(self, mock_load_image):
        mock_load_image.return_value = np.zeros((100, 100, 3), dtype=np.uint8)

        pipeline = Pipeline(config={'continue_on_error': False})
        failing_analyzer = MockAnalyzer(should_fail=True)
        working_analyzer = MockAnalyzer()

        pipeline.add_stage("failing", failing_analyzer)
        pipeline.add_stage("working", working_analyzer)

        panel = Panel("p1", "ep001", 1, "test.jpg", 800, 1200)
        result = pipeline.process_panel(panel)

        # Only first stage should have been attempted
        assert failing_analyzer.call_count == 1
        assert working_analyzer.call_count == 0

    @patch('core.pipeline.Pipeline._load_image')
    def test_process_panels_serial(self, mock_load_image):
        mock_load_image.return_value = np.zeros((100, 100, 3), dtype=np.uint8)

        pipeline = Pipeline()
        analyzer = MockAnalyzer()
        pipeline.add_stage("test", analyzer)

        panels = [
            Panel("p1", "ep001", 1, "test1.jpg", 800, 1200),
            Panel("p2", "ep001", 2, "test2.jpg", 800, 1200),
        ]

        results = pipeline.process_panels(panels, parallel=False)

        assert len(results) == 2
        assert analyzer.call_count == 2


class TestPipelineBuilder:
    """Test PipelineBuilder."""

    def test_creation(self):
        builder = PipelineBuilder()
        assert len(builder.stages) == 0

    def test_add_character_detection(self):
        builder = PipelineBuilder()
        analyzer = MockAnalyzer()
        builder.add_character_detection(analyzer)

        assert len(builder.stages) == 1
        assert builder.stages[0][0] == "character_detection"

    def test_add_emotion_detection(self):
        builder = PipelineBuilder()
        analyzer = MockAnalyzer()
        builder.add_emotion_detection(analyzer)

        # Should have dependency on character_detection
        assert len(builder.stages) == 1
        assert builder.stages[0][2] == ["character_detection"]

    def test_fluent_interface(self):
        analyzer = MockAnalyzer()
        builder = (PipelineBuilder()
            .add_character_detection(analyzer)
            .add_emotion_detection(analyzer)
            .configure(max_workers=8)
        )

        assert len(builder.stages) == 2
        assert builder.config['max_workers'] == 8

    def test_build(self):
        analyzer = MockAnalyzer()
        pipeline = (PipelineBuilder()
            .add_character_detection(analyzer)
            .add_visual_analysis(analyzer)
            .configure(max_workers=2)
            .build()
        )

        assert isinstance(pipeline, Pipeline)
        assert len(pipeline.stages) == 2
        assert pipeline.max_workers == 2


class TestPipelineContext:
    """Test PipelineContext."""

    def test_creation(self):
        panel = Panel("p1", "ep001", 1, "test.jpg", 800, 1200)
        context = PipelineContext(panel=panel)

        assert context.panel == panel
        assert context.image is None
        assert len(context.intermediate_results) == 0
        assert len(context.stage_results) == 0

    def test_add_intermediate_results(self):
        panel = Panel("p1", "ep001", 1, "test.jpg", 800, 1200)
        context = PipelineContext(panel=panel)

        result = AnalysisResult(characters=[Character("Test", 0.9)])
        context.intermediate_results["test_stage"] = result

        assert "test_stage" in context.intermediate_results
        assert len(context.intermediate_results["test_stage"].characters) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
