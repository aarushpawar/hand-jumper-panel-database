"""
Configuration management module.

Loads and manages YAML configuration files, providing a unified
interface to all application settings.
"""

from pathlib import Path
from typing import Any, Dict, Optional
import yaml


class Config:
    """
    Configuration manager for the Hand Jumper database.

    Loads YAML configuration files and provides dot-notation access
    to nested configuration values.

    Example:
        >>> config = Config('panel_detection')
        >>> min_height = config.get('detection.min_panel_height', default=200)
        >>> print(min_height)
        200
    """

    def __init__(self, config_name: str, config_dir: Optional[Path] = None):
        """
        Initialize configuration from YAML file.

        Args:
            config_name: Name of config file (without .yaml extension)
            config_dir: Directory containing config files (default: project_root/config)
        """
        if config_dir is None:
            # Auto-detect project root
            current = Path(__file__).parent
            project_root = current.parent.parent  # scraper/core -> project root
            config_dir = project_root / 'config'

        self.config_dir = Path(config_dir)
        self.config_file = self.config_dir / f"{config_name}.yaml"
        self._data: Dict[str, Any] = {}

        self._load()

    def _load(self) -> None:
        """Load configuration from YAML file."""
        if not self.config_file.exists():
            raise FileNotFoundError(
                f"Configuration file not found: {self.config_file}"
            )

        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                self._data = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ValueError(
                f"Invalid YAML in configuration file {self.config_file}: {e}"
            )

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation.

        Args:
            key: Configuration key (e.g., 'detection.min_panel_height')
            default: Default value if key not found

        Returns:
            Configuration value or default

        Example:
            >>> config.get('detection.overlap.enabled', False)
            True
        """
        keys = key.split('.')
        value = self._data

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def get_section(self, section: str) -> Dict[str, Any]:
        """
        Get entire configuration section.

        Args:
            section: Section name (top-level key)

        Returns:
            Dictionary containing section data

        Example:
            >>> overlap_config = config.get_section('overlap')
        """
        return self._data.get(section, {})

    def set(self, key: str, value: Any) -> None:
        """
        Set configuration value (runtime only, not saved to file).

        Args:
            key: Configuration key in dot notation
            value: Value to set
        """
        keys = key.split('.')
        data = self._data

        for k in keys[:-1]:
            if k not in data:
                data[k] = {}
            data = data[k]

        data[keys[-1]] = value

    def reload(self) -> None:
        """Reload configuration from file."""
        self._load()

    @property
    def data(self) -> Dict[str, Any]:
        """Get raw configuration data."""
        return self._data.copy()

    def __repr__(self) -> str:
        return f"Config(file='{self.config_file}')"


def load_config(config_name: str, config_dir: Optional[Path] = None) -> Config:
    """
    Load configuration file.

    Convenience function for creating Config instances.

    Args:
        config_name: Name of config file (without .yaml)
        config_dir: Directory containing config files

    Returns:
        Config instance

    Example:
        >>> config = load_config('panel_detection')
        >>> min_height = config.get('detection.min_panel_height')
    """
    return Config(config_name, config_dir)


# Singleton instances for commonly used configs
_config_cache: Dict[str, Config] = {}


def get_config(config_name: str, reload: bool = False) -> Config:
    """
    Get cached configuration instance.

    Args:
        config_name: Name of config file
        reload: Force reload from file

    Returns:
        Cached Config instance
    """
    if reload or config_name not in _config_cache:
        _config_cache[config_name] = load_config(config_name)

    return _config_cache[config_name]
