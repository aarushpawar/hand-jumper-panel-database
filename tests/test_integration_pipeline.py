"""
Integration tests for full pipeline execution.
"""

import pytest
import numpy as np
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

from core.pipeline import PipelineBuilder, Pipeline
from core.models import Panel, Episode, Database
from core.feature_flags import FeatureFlags
from analyzers import ColorAnalyzer, FaceRecognitionJSONAnalyzer


class TestPipelineIntegration:
    """Integration tests for complete pipeline."""

    def test_single_panel_through_visual_pipeline(self):
        """Test processing a single panel through visual analysis."""
        # Create test panel
        panel = Panel(
            id="test_p001",
            episode="test_ep001",
            panel_number=1,
            path="test.jpg",
            width=800,
            height=1200
        )

        # Build pipeline with only visual analysis (no external dependencies)
        pipeline = (PipelineBuilder()
            .add_visual_analysis(ColorAnalyzer())
            .configure(max_workers=1)
            .build()
        )

        # Mock image loading
        test_image = np.zeros((1200, 800, 3), dtype=np.uint8)
        test_image[0:600, :, :] = [100, 150, 200]  # Add some color

        with patch.object(Pipeline, '_load_image', return_value=test_image):
            result = pipeline.process_panel(panel)

        # Verify analysis was performed
        assert result.ai_analysis is not None
        assert result.ai_analysis.visual is not None
        assert len(result.ai_analysis.visual.dominant_colors) > 0

    def test_multiple_panels_serial_processing(self):
        """Test processing multiple panels serially."""
        panels = [
            Panel(f"p{i}", "ep001", i, f"p{i}.jpg", 800, 1200)
            for i in range(3)
        ]

        pipeline = (PipelineBuilder()
            .add_visual_analysis(ColorAnalyzer())
            .configure(max_workers=1)
            .build()
        )

        test_image = np.ones((1200, 800, 3), dtype=np.uint8) * 100

        with patch.object(Pipeline, '_load_image', return_value=test_image):
            results = pipeline.process_panels(panels, parallel=False)

        assert len(results) == 3
        assert all(p.ai_analysis is not None for p in results)

    def test_pipeline_with_missing_dependencies(self):
        """Test pipeline behavior when analyzer dependencies are missing."""
        pipeline = (PipelineBuilder()
            .add_character_detection(FaceRecognitionJSONAnalyzer())
            .add_visual_analysis(ColorAnalyzer())
            .configure(continue_on_error=True)
            .build()
        )

        panel = Panel("p1", "ep001", 1, "p1.jpg", 800, 1200)
        test_image = np.zeros((1200, 800, 3), dtype=np.uint8)

        with patch.object(Pipeline, '_load_image', return_value=test_image):
            result = pipeline.process_panel(panel)

        # Should still have visual analysis even if face recognition fails
        assert result.ai_analysis is not None

    def test_pipeline_builder_fluent_interface(self):
        """Test builder pattern creates valid pipeline."""
        pipeline = (PipelineBuilder()
            .add_visual_analysis(ColorAnalyzer())
            .configure(max_workers=2, continue_on_error=True)
            .build()
        )

        assert isinstance(pipeline, Pipeline)
        assert len(pipeline.stages) == 1
        assert pipeline.max_workers == 2
        assert pipeline.continue_on_error is True

    def test_episode_processing(self):
        """Test processing all panels in an episode."""
        panels = [
            Panel(f"ep001_p{i:03d}", "ep001", i, f"p{i}.jpg", 800, 1200)
            for i in range(5)
        ]

        episode = Episode(id="ep001", number=1, title="Test Episode", panels=panels)

        pipeline = (PipelineBuilder()
            .add_visual_analysis(ColorAnalyzer())
            .build()
        )

        test_image = np.ones((1200, 800, 3), dtype=np.uint8) * 100

        with patch.object(Pipeline, '_load_image', return_value=test_image):
            processed_panels = pipeline.process_panels(episode.panels, parallel=False)

        episode.panels = processed_panels

        # Verify all panels processed
        assert len(episode.panels) == 5
        assert all(p.ai_analysis is not None for p in episode.panels)


class TestDatabaseIntegration:
    """Integration tests for database operations."""

    def test_database_creation_and_save(self, tmp_path):
        """Test creating and saving database."""
        panels = [Panel(f"p{i}", "ep001", i, f"p{i}.jpg", 800, 1200) for i in range(3)]
        episode = Episode(id="ep001", number=1, panels=panels)
        db = Database(episodes=[episode])

        # Save database
        db_path = tmp_path / "test_db.json"
        db.save(str(db_path))

        # Verify file was created
        assert db_path.exists()

        # Verify content
        with open(db_path, 'r') as f:
            data = json.load(f)

        assert data['version'] == "2.0"
        assert data['total_episodes'] == 1
        assert data['total_panels'] == 3

    def test_database_with_analysis_results(self, tmp_path):
        """Test database with AI analysis results."""
        from core.models import AnalysisResult, VisualProperties

        panel = Panel("p1", "ep001", 1, "p1.jpg", 800, 1200)
        panel.ai_analysis = AnalysisResult(
            visual=VisualProperties(
                dominant_colors=[[100, 150, 200]],
                brightness=0.5,
                contrast=0.3
            )
        )

        episode = Episode(id="ep001", number=1, panels=[panel])
        db = Database(episodes=[episode])

        db_path = tmp_path / "test_db.json"
        db.save(str(db_path))

        # Load and verify
        with open(db_path, 'r') as f:
            data = json.load(f)

        panel_data = data['episodes'][0]['panels'][0]
        assert panel_data['ai_analysis'] is not None
        assert panel_data['ai_analysis']['visual'] is not None


class TestFeatureFlagIntegration:
    """Integration tests with feature flags."""

    def test_feature_flags_control_pipeline(self, tmp_path):
        """Test that feature flags correctly enable/disable analyzers."""
        # Create feature flags config
        config_path = tmp_path / "features.json"
        config = {
            'visual_analysis': {'state': 'enabled', 'config': {}},
            'face_recognition': {'state': 'disabled', 'config': {}}
        }

        with open(config_path, 'w') as f:
            json.dump(config, f)

        flags = FeatureFlags(config_path)

        # Build pipeline based on flags
        builder = PipelineBuilder()

        if flags.is_enabled('visual_analysis'):
            builder.add_visual_analysis(ColorAnalyzer())

        if flags.is_enabled('face_recognition'):
            builder.add_character_detection(FaceRecognitionJSONAnalyzer())

        pipeline = builder.build()

        # Should only have visual analysis
        assert len(pipeline.stages) == 1
        assert pipeline.stages[0].name == "visual_analysis"


class TestEndToEndScenario:
    """End-to-end integration test scenarios."""

    def test_complete_workflow(self, tmp_path):
        """Test complete workflow from panels to saved database."""
        # 1. Create panels
        panels = [
            Panel(f"ep001_p{i:03d}", "ep001", i, f"test_{i}.jpg", 800, 1200)
            for i in range(3)
        ]

        # 2. Create episode
        episode = Episode(id="ep001", number=1, title="Test Episode", panels=panels)

        # 3. Process through pipeline
        pipeline = (PipelineBuilder()
            .add_visual_analysis(ColorAnalyzer())
            .configure(max_workers=1, continue_on_error=True)
            .build()
        )

        test_image = np.ones((1200, 800, 3), dtype=np.uint8) * 100

        with patch.object(Pipeline, '_load_image', return_value=test_image):
            processed_panels = pipeline.process_panels(episode.panels, parallel=False)

        episode.panels = processed_panels

        # 4. Create database
        db = Database(episodes=[episode])

        # 5. Save database
        db_path = tmp_path / "final_db.json"
        db.save(str(db_path))

        # 6. Verify complete workflow
        assert db_path.exists()

        with open(db_path, 'r') as f:
            data = json.load(f)

        assert data['total_episodes'] == 1
        assert data['total_panels'] == 3

        # Check that panels have analysis
        for panel in data['episodes'][0]['panels']:
            assert panel['ai_analysis'] is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
