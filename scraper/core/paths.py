"""
Path management utilities.

Centralizes all path resolution and provides consistent path handling
across the project. Ensures paths work across different operating systems.
"""

from pathlib import Path
from typing import Optional
from .config import load_config


class PathManager:
    """
    Manages all file paths used in the project.

    Loads paths from configuration and provides methods to resolve
    absolute paths at runtime. All paths are returned as pathlib.Path objects.

    Example:
        >>> paths = PathManager()
        >>> panels_dir = paths.get('data.panels_original')
        >>> print(panels_dir)
        /home/user/hand-jumper-panel-database/data/panels_original
    """

    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize path manager.

        Args:
            config_dir: Directory containing config files
        """
        # Auto-detect project root
        current = Path(__file__).parent
        self.project_root = (current.parent.parent).resolve()

        # Load paths configuration
        self.config = load_config('paths', config_dir)

        # Ensure base directories exist
        self._ensure_base_dirs()

    def _ensure_base_dirs(self) -> None:
        """Create base directories if they don't exist."""
        base_dirs = ['data_dir', 'config_dir', 'logs_dir']
        for dir_name in base_dirs:
            dir_path = self.get(f'base.{dir_name}')
            if dir_path:
                try:
                    dir_path.mkdir(parents=True, exist_ok=True)
                except OSError as e:
                    # Log warning but don't fail - directory creation is best-effort
                    print(f"Warning: Could not create directory {dir_path}: {e}")

    def get(self, key: str, create: bool = False) -> Optional[Path]:
        """
        Get absolute path for a configuration key.

        Args:
            key: Path key in dot notation (e.g., 'data.panels_original')
            create: Whether to create the directory if it doesn't exist

        Returns:
            Absolute Path object, or None if key not found

        Example:
            >>> panels_dir = paths.get('data.panels_original', create=True)
        """
        relative_path = self.config.get(key)

        if relative_path is None:
            return None

        # Convert to Path and resolve relative to project root
        abs_path = (self.project_root / relative_path).resolve()

        if create and not abs_path.exists():
            # Check if it's meant to be a directory (no extension)
            if not abs_path.suffix:
                abs_path.mkdir(parents=True, exist_ok=True)
            else:
                # It's a file, create parent directory
                abs_path.parent.mkdir(parents=True, exist_ok=True)

        return abs_path

    def get_relative(self, key: str) -> Optional[Path]:
        """
        Get path relative to project root.

        Args:
            key: Path key in dot notation

        Returns:
            Relative Path object, or None if key not found
        """
        relative_path = self.config.get(key)

        if relative_path is None:
            return None

        return Path(relative_path)

    def to_relative(self, absolute_path: Path) -> Path:
        """
        Convert absolute path to relative path from project root.

        Args:
            absolute_path: Absolute path to convert

        Returns:
            Path relative to project root

        Example:
            >>> abs_path = Path('/home/user/project/data/panels/ep001.jpg')
            >>> rel_path = paths.to_relative(abs_path)
            >>> print(rel_path)
            data/panels/ep001.jpg
        """
        absolute_path = Path(absolute_path).resolve()

        try:
            return absolute_path.relative_to(self.project_root)
        except ValueError:
            # Path is outside project root, return as-is
            return absolute_path

    def resolve(self, path: Path) -> Path:
        """
        Resolve a path relative to project root.

        If path is already absolute, returns it as-is.
        If path is relative, resolves it relative to project root.

        Args:
            path: Path to resolve

        Returns:
            Absolute Path object
        """
        path = Path(path)

        if path.is_absolute():
            return path.resolve()

        return (self.project_root / path).resolve()

    @property
    def root(self) -> Path:
        """Get project root directory."""
        return self.project_root

    def __repr__(self) -> str:
        return f"PathManager(root='{self.project_root}')"


# Singleton instance
_path_manager: Optional[PathManager] = None


def get_path_manager() -> PathManager:
    """
    Get singleton PathManager instance.

    Returns:
        PathManager instance
    """
    global _path_manager
    if _path_manager is None:
        _path_manager = PathManager()
    return _path_manager
