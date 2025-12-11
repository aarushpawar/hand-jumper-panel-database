"""
Content analysis for boundary validation.

Analyzes image content to validate whether a proposed boundary
is actually a safe split point (no text or objects crossing).
"""

from typing import List, Tuple, Optional
import numpy as np
import cv2


class ContentAnalyzer:
    """
    Analyzes image content around boundaries to validate splits.
    """

    def __init__(self, config: dict):
        """
        Initialize analyzer with configuration.

        Args:
            config: Configuration dictionary from panel_splitting.yaml
        """
        self.config = config
        self.validation_config = config.get('validation', {})
        self.processing_config = config.get('processing', {})

    def validate_boundary(self, image: np.ndarray, y_position: int) -> Tuple[bool, str]:
        """
        Validate whether a boundary is safe for splitting.

        Args:
            image: Input image
            y_position: Proposed boundary Y coordinate

        Returns:
            Tuple of (is_valid, reason)
            - is_valid: True if boundary is safe to use
            - reason: Human-readable reason for decision
        """
        height, width = image.shape[:2]

        # Boundary must be within image
        if y_position < 0 or y_position >= height:
            return False, "boundary outside image"

        # Check for text crossing
        if self.validation_config.get('text_buffer', 100) > 0:
            has_text_crossing = self._check_text_crossing(image, y_position)
            if has_text_crossing:
                return False, "text crosses boundary"

        # Check for edge crossing (objects/content spanning boundary)
        if self.validation_config.get('edge_crossing', True):
            has_edge_crossing = self._check_edge_crossing(image, y_position)
            if has_edge_crossing:
                return False, "content crosses boundary"

        return True, "valid"

    def _check_text_crossing(self, image: np.ndarray, y_position: int) -> bool:
        """
        Check if text regions cross the boundary.

        Uses connected component analysis to detect text-like regions.

        Args:
            image: Input image
            y_position: Boundary Y coordinate

        Returns:
            True if text likely crosses boundary
        """
        height, width = image.shape[:2]
        buffer = self.validation_config.get('text_buffer', 100)

        # Define region to check
        y_min = max(0, y_position - buffer)
        y_max = min(height, y_position + buffer)

        if y_max - y_min < 10:
            return False

        region = image[y_min:y_max, :]
        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)

        # Binarize (text is usually dark on light or light on dark)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        _, binary_inv = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        # Find connected components in both versions
        for binary_img in [binary, binary_inv]:
            num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(binary_img, connectivity=8)

            for i in range(1, num_labels):  # Skip background (0)
                x, y, w, h, area = stats[i]

                # Text-like characteristics:
                # - Moderate size (not too small, not too large)
                # - Aspect ratio more horizontal than vertical (typical for text)
                # - Located near the boundary

                if 50 < area < 5000:  # Reasonable text size
                    aspect_ratio = w / h if h > 0 else 0

                    # Check if this component crosses the boundary
                    component_y_min = y_min + y
                    component_y_max = y_min + y + h

                    # Does it cross the boundary?
                    if component_y_min < y_position < component_y_max:
                        # Additional check: is it text-like?
                        if 0.3 < aspect_ratio < 15:  # Text is usually wider than tall
                            return True

        return False

    def _check_edge_crossing(self, image: np.ndarray, y_position: int) -> bool:
        """
        Check if strong edges (content) cross the boundary.

        Args:
            image: Input image
            y_position: Boundary Y coordinate

        Returns:
            True if edges cross boundary
        """
        height, width = image.shape[:2]
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Detect edges
        edge_config = self.processing_config.get('edge_detection', {})
        canny_low = edge_config.get('canny_low', 30)
        canny_high = edge_config.get('canny_high', 100)
        edges = cv2.Canny(gray, canny_low, canny_high)

        # Check buffer zone around boundary
        buffer = 10
        y_min = max(0, y_position - buffer)
        y_max = min(height, y_position + buffer)

        buffer_region = edges[y_min:y_max, :]

        # Count vertical edges in the buffer zone
        # Vertical edges suggest content flowing across the boundary
        sobel_x = cv2.Sobel(buffer_region, cv2.CV_64F, 1, 0, ksize=3)
        vertical_edge_strength = np.sum(np.abs(sobel_x))

        # Threshold: if there's significant vertical edge activity, content is crossing
        threshold = width * buffer * 5  # Tunable threshold
        return vertical_edge_strength > threshold

    def analyze_content_density(self, image: np.ndarray) -> np.ndarray:
        """
        Calculate content density per row.

        Args:
            image: Input image

        Returns:
            Array of content density values (0.0-1.0) per row
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Content = non-white pixels
        # Invert so that lower brightness = more content
        row_brightness = np.mean(gray, axis=1)
        content_density = (255 - row_brightness) / 255.0

        return content_density

    def find_text_regions(self, image: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """
        Find bounding boxes of potential text regions.

        Args:
            image: Input image

        Returns:
            List of (x, y, width, height) bounding boxes
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Binarize
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        # Find connected components
        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)

        text_regions = []
        for i in range(1, num_labels):
            x, y, w, h, area = stats[i]

            # Filter for text-like regions
            if 50 < area < 10000:  # Reasonable size
                aspect_ratio = w / h if h > 0 else 0
                if 0.3 < aspect_ratio < 20:  # Text-like aspect ratio
                    text_regions.append((x, y, w, h))

        return text_regions
