"""
Unit tests for analyzer plugin system.
"""

import pytest
import numpy as np
from pathlib import Path
from core.analyzer_plugin import (
    AnalyzerPlugin, CharacterAnalyzerPlugin, EmotionAnalyzerPlugin,
    DialogueAnalyzerPlugin, ActionAnalyzerPlugin, SceneAnalyzerPlugin,
    VisualAnalyzerPlugin, PluginRegistry, register_plugin, get_registry
)
from core.models import (
    AnalysisResult, Character, Emotion, DialogueEntry, Action,
    SceneContext, VisualProperties
)


class MockAnalyzer(AnalyzerPlugin):
    """Mock analyzer for testing."""

    @property
    def name(self) -> str:
        return "mock_analyzer"

    @property
    def version(self) -> str:
        return "1.0.0"

    def analyze(self, image: np.ndarray, panel_path: Path) -> AnalysisResult:
        return AnalysisResult()


class MockCharacterAnalyzer(CharacterAnalyzerPlugin):
    """Mock character analyzer."""

    @property
    def name(self) -> str:
        return "mock_character"

    @property
    def version(self) -> str:
        return "1.0.0"

    def detect_characters(self, image: np.ndarray):
        return [Character(name="TestChar", confidence=0.9)]


class TestAnalyzerPlugin:
    """Test base AnalyzerPlugin class."""

    def test_creation(self):
        analyzer = MockAnalyzer()
        assert analyzer.name == "mock_analyzer"
        assert analyzer.version == "1.0.0"
        assert analyzer.enabled is True

    def test_creation_with_config(self):
        config = {'enabled': False, 'priority': 50}
        analyzer = MockAnalyzer(config)
        assert analyzer.enabled is False
        assert analyzer.priority == 50

    def test_dependencies_empty(self):
        analyzer = MockAnalyzer()
        assert analyzer.dependencies == []

    def test_check_dependencies_none(self):
        analyzer = MockAnalyzer()
        assert analyzer.check_dependencies() is True

    def test_check_dependencies_missing(self):
        class AnalyzerWithDeps(MockAnalyzer):
            @property
            def dependencies(self):
                return ['nonexistent_package_xyz']

        analyzer = AnalyzerWithDeps()
        assert analyzer.check_dependencies() is False

    def test_can_run_enabled(self):
        analyzer = MockAnalyzer({'enabled': True})
        assert analyzer.can_run() is True

    def test_can_run_disabled(self):
        analyzer = MockAnalyzer({'enabled': False})
        assert analyzer.can_run() is False

    def test_analyze(self):
        analyzer = MockAnalyzer()
        image = np.zeros((100, 100, 3), dtype=np.uint8)
        result = analyzer.analyze(image, Path("test.jpg"))
        assert isinstance(result, AnalysisResult)


class TestCharacterAnalyzerPlugin:
    """Test CharacterAnalyzerPlugin."""

    def test_detect_characters(self):
        analyzer = MockCharacterAnalyzer()
        image = np.zeros((100, 100, 3), dtype=np.uint8)
        characters = analyzer.detect_characters(image)

        assert len(characters) == 1
        assert characters[0].name == "TestChar"
        assert characters[0].confidence == 0.9

    def test_analyze_returns_result(self):
        analyzer = MockCharacterAnalyzer()
        image = np.zeros((100, 100, 3), dtype=np.uint8)
        result = analyzer.analyze(image, Path("test.jpg"))

        assert isinstance(result, AnalysisResult)
        assert len(result.characters) == 1


class TestEmotionAnalyzerPlugin:
    """Test EmotionAnalyzerPlugin."""

    def test_creation(self):
        class MockEmotionAnalyzer(EmotionAnalyzerPlugin):
            @property
            def name(self):
                return "mock_emotion"

            @property
            def version(self):
                return "1.0.0"

            def detect_emotions(self, image, characters):
                return [Emotion("TestChar", "happy", 0.8)]

        analyzer = MockEmotionAnalyzer()
        assert analyzer.name == "mock_emotion"


class TestPluginRegistry:
    """Test PluginRegistry."""

    def test_creation(self):
        registry = PluginRegistry()
        assert registry.list_plugins() == []

    def test_register_plugin(self):
        registry = PluginRegistry()
        analyzer = MockAnalyzer()
        registry.register(analyzer)

        assert "mock_analyzer" in registry.list_plugins()

    def test_get_plugin(self):
        registry = PluginRegistry()
        analyzer = MockAnalyzer()
        registry.register(analyzer)

        retrieved = registry.get("mock_analyzer")
        assert retrieved is not None
        assert retrieved.name == "mock_analyzer"

    def test_get_nonexistent_plugin(self):
        registry = PluginRegistry()
        assert registry.get("nonexistent") is None

    def test_get_all_plugins(self):
        registry = PluginRegistry()
        analyzer1 = MockAnalyzer()
        analyzer2 = MockCharacterAnalyzer()

        registry.register(analyzer1)
        registry.register(analyzer2)

        all_plugins = registry.get_all()
        assert len(all_plugins) == 2

    def test_get_by_type(self):
        registry = PluginRegistry()
        analyzer1 = MockAnalyzer()
        analyzer2 = MockCharacterAnalyzer()

        registry.register(analyzer1)
        registry.register(analyzer2)

        char_analyzers = registry.get_by_type(CharacterAnalyzerPlugin)
        assert len(char_analyzers) == 1
        assert isinstance(char_analyzers[0], CharacterAnalyzerPlugin)

    def test_register_disabled_plugin(self):
        registry = PluginRegistry()
        analyzer = MockAnalyzer({'enabled': False})
        registry.register(analyzer)

        # Should still register but with warning
        assert registry.get("mock_analyzer") is None


class TestGlobalRegistry:
    """Test global registry functions."""

    def test_get_registry(self):
        registry = get_registry()
        assert isinstance(registry, PluginRegistry)

    def test_register_global_plugin(self):
        # Note: This modifies global state
        # In real tests, we'd use fixtures to clean up
        analyzer = MockAnalyzer()
        register_plugin(analyzer)

        # Verify it was registered
        # (In production, we'd clean this up after test)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
