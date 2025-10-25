"""
Unit tests for feature flag system.
"""

import pytest
import json
import tempfile
from pathlib import Path
from core.feature_flags import FeatureFlags, FeatureState, get_feature_flags


class TestFeatureFlags:
    """Test FeatureFlags class."""

    def test_creation_no_config(self):
        """Test creation when config doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "features.json"
            flags = FeatureFlags(config_path)

            # Should use defaults
            assert 'face_recognition' in flags.flags
            assert 'emotion_detection' in flags.flags

    def test_creation_with_config(self):
        """Test creation with existing config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "features.json"

            # Create test config
            test_config = {
                'test_feature': {
                    'state': 'enabled',
                    'config': {'param': 123}
                }
            }
            config_path.write_text(json.dumps(test_config))

            flags = FeatureFlags(config_path)
            assert 'test_feature' in flags.flags

    def test_creation_with_invalid_json(self):
        """Test creation with corrupted JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "features.json"
            config_path.write_text("{ invalid json }")

            flags = FeatureFlags(config_path)
            # Should fall back to defaults
            assert 'face_recognition' in flags.flags

    def test_is_enabled_true(self):
        """Test checking if feature is enabled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "features.json"
            flags = FeatureFlags(config_path)

            assert flags.is_enabled('face_recognition') is True

    def test_is_enabled_false(self):
        """Test checking disabled feature."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "features.json"
            flags = FeatureFlags(config_path)
            flags.disable('face_recognition')

            assert flags.is_enabled('face_recognition') is False

    def test_is_enabled_experimental(self):
        """Test experimental features are considered enabled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "features.json"
            flags = FeatureFlags(config_path)
            flags.set_experimental('face_recognition')

            assert flags.is_enabled('face_recognition') is True

    def test_is_experimental(self):
        """Test checking if feature is experimental."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "features.json"
            flags = FeatureFlags(config_path)

            assert flags.is_experimental('action_detection') is True

    def test_get_config(self):
        """Test getting feature configuration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "features.json"
            flags = FeatureFlags(config_path)

            config = flags.get_config('face_recognition')
            assert 'tolerance' in config
            assert config['tolerance'] == 0.6

    def test_get_config_nonexistent(self):
        """Test getting config for nonexistent feature."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "features.json"
            flags = FeatureFlags(config_path)

            config = flags.get_config('nonexistent_feature')
            assert config == {}

    def test_enable_existing_feature(self):
        """Test enabling a feature."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "features.json"
            flags = FeatureFlags(config_path)

            flags.disable('face_recognition')
            assert flags.is_enabled('face_recognition') is False

            flags.enable('face_recognition')
            assert flags.is_enabled('face_recognition') is True

    def test_enable_new_feature(self):
        """Test enabling a new feature that doesn't exist yet."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "features.json"
            flags = FeatureFlags(config_path)

            flags.enable('new_feature', config={'param': 'value'})
            assert flags.is_enabled('new_feature') is True
            assert flags.get_config('new_feature')['param'] == 'value'

    def test_disable_feature(self):
        """Test disabling a feature."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "features.json"
            flags = FeatureFlags(config_path)

            flags.disable('face_recognition')
            assert flags.is_enabled('face_recognition') is False

            # Verify it was saved
            flags2 = FeatureFlags(config_path)
            assert flags2.is_enabled('face_recognition') is False

    def test_set_experimental(self):
        """Test marking feature as experimental."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "features.json"
            flags = FeatureFlags(config_path)

            flags.set_experimental('face_recognition')
            assert flags.is_experimental('face_recognition') is True
            assert flags.is_enabled('face_recognition') is True

    def test_list_features(self):
        """Test listing all features."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "features.json"
            flags = FeatureFlags(config_path)

            features = flags.list_features()
            assert 'face_recognition' in features
            assert 'emotion_detection' in features
            assert features['face_recognition'] == 'enabled'

    def test_persistence(self):
        """Test that changes are persisted to disk."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "features.json"

            # Create and modify
            flags1 = FeatureFlags(config_path)
            flags1.enable('test_feature', config={'value': 42})

            # Load again
            flags2 = FeatureFlags(config_path)
            assert flags2.is_enabled('test_feature') is True
            assert flags2.get_config('test_feature')['value'] == 42


class TestFeatureState:
    """Test FeatureState enum."""

    def test_enum_values(self):
        assert FeatureState.ENABLED.value == "enabled"
        assert FeatureState.DISABLED.value == "disabled"
        assert FeatureState.EXPERIMENTAL.value == "experimental"


class TestGlobalFeatureFlags:
    """Test global feature flags singleton."""

    def test_get_feature_flags(self):
        """Test global instance."""
        flags = get_feature_flags()
        assert isinstance(flags, FeatureFlags)

        # Should return same instance
        flags2 = get_feature_flags()
        assert flags is flags2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
