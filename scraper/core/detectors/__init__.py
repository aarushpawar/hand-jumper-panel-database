"""Panel detection components."""

from .boundary_detector import BoundaryDetector, Boundary
from .content_analyzer import ContentAnalyzer
from .overlap_calculator import OverlapCalculator

__all__ = [
    'BoundaryDetector',
    'Boundary',
    'ContentAnalyzer',
    'OverlapCalculator',
]
