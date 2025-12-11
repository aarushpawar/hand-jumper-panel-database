"""
Adaptive overlap calculation for panel extraction.

Determines how much overlap to add when extracting panels
based on boundary confidence and local content.
"""

import numpy as np
import cv2
from typing import Tuple


class OverlapCalculator:
    """
    Calculates adaptive overlap amounts for panel boundaries.

    Higher overlap for lower confidence boundaries to prevent content loss.
    """

    def __init__(self, config: dict):
        """
        Initialize calculator with configuration.

        Args:
            config: Configuration dictionary from panel_splitting.yaml
        """
        self.config = config
        self.overlap_config = config.get('overlap', {})

        self.min_overlap = self.overlap_config.get('min', 20)
        self.max_overlap = self.overlap_config.get('max', 150)
        self.adaptive = self.overlap_config.get('adaptive', True)

        # Confidence-based defaults
        self.high_conf_overlap = self.overlap_config.get('high_confidence', 25)
        self.medium_conf_overlap = self.overlap_config.get('medium_confidence', 50)
        self.low_conf_overlap = self.overlap_config.get('low_confidence', 100)

    def calculate_overlap(
        self,
        image: np.ndarray,
        boundary_y: int,
        confidence: float,
        direction: str = 'both'
    ) -> Tuple[int, int]:
        """
        Calculate overlap for a boundary.

        Args:
            image: Input image
            boundary_y: Y coordinate of boundary
            confidence: Boundary confidence score (0.0-1.0)
            direction: 'top', 'bottom', or 'both'

        Returns:
            Tuple of (overlap_top, overlap_bottom) in pixels
        """
        if not self.adaptive:
            # Fixed overlap based on confidence tiers
            overlap = self._get_fixed_overlap(confidence)
            return (overlap, overlap)

        # Adaptive overlap based on content
        overlap_top = self._calculate_directional_overlap(
            image, boundary_y, confidence, 'top'
        )
        overlap_bottom = self._calculate_directional_overlap(
            image, boundary_y, confidence, 'bottom'
        )

        # Clamp to min/max
        overlap_top = max(self.min_overlap, min(self.max_overlap, overlap_top))
        overlap_bottom = max(self.min_overlap, min(self.max_overlap, overlap_bottom))

        if direction == 'top':
            return (overlap_top, 0)
        elif direction == 'bottom':
            return (0, overlap_bottom)
        else:
            return (overlap_top, overlap_bottom)

    def _get_fixed_overlap(self, confidence: float) -> int:
        """
        Get fixed overlap based on confidence tier.

        Args:
            confidence: Boundary confidence (0.0-1.0)

        Returns:
            Overlap in pixels
        """
        if confidence >= 0.8:
            return self.high_conf_overlap
        elif confidence >= 0.5:
            return self.medium_conf_overlap
        else:
            return self.low_conf_overlap

    def _calculate_directional_overlap(
        self,
        image: np.ndarray,
        boundary_y: int,
        confidence: float,
        direction: str
    ) -> int:
        """
        Calculate overlap in one direction based on content.

        Args:
            image: Input image
            boundary_y: Y coordinate of boundary
            confidence: Boundary confidence
            direction: 'top' or 'bottom'

        Returns:
            Overlap in pixels
        """
        height = image.shape[0]

        # Start with confidence-based baseline
        base_overlap = self._get_fixed_overlap(confidence)

        # Extend overlap until we hit whitespace or reach max
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        if direction == 'top':
            # Search upward
            search_start = max(0, boundary_y - self.max_overlap)
            search_end = boundary_y
            search_range = range(search_end, search_start, -1)
        else:
            # Search downward
            search_start = boundary_y
            search_end = min(height, boundary_y + self.max_overlap)
            search_range = range(search_start, search_end)

        # Find first row that's mostly white
        white_threshold = 240
        for y in search_range:
            if y < 0 or y >= height:
                continue

            row = gray[y, :]
            white_percent = np.sum(row > white_threshold) / row.size

            if white_percent > 0.95:
                # Found whitespace, calculate overlap to here
                overlap = abs(y - boundary_y)
                return max(base_overlap, overlap)

        # Didn't find whitespace, use base overlap
        return base_overlap

    def calculate_panel_bounds(
        self,
        image_height: int,
        boundaries: list,
        panel_index: int
    ) -> Tuple[int, int]:
        """
        Calculate final panel bounds including overlap.

        Args:
            image_height: Total image height
            boundaries: List of boundary y positions
            panel_index: Index of panel to extract (0-based)

        Returns:
            Tuple of (y_start, y_end) with overlap applied
        """
        # Determine base bounds
        if panel_index == 0:
            y_start = 0
        else:
            y_start = boundaries[panel_index - 1]

        if panel_index >= len(boundaries):
            y_end = image_height
        else:
            y_end = boundaries[panel_index]

        # No overlap needed - will be calculated per boundary
        return (y_start, y_end)
