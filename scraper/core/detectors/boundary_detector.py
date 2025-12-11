"""
Multi-signal boundary detection for panel splitting.

Combines multiple detection signals to find panel boundaries:
- Whitespace gaps (traditional brightness-based)
- Border lines (horizontal separators)
- Content breaks (sudden density changes)
- Color shifts (palette changes)
"""

from dataclasses import dataclass
from typing import List, Tuple
import numpy as np
import cv2


@dataclass
class Boundary:
    """Represents a potential panel boundary."""
    y_position: int          # Y coordinate of boundary
    confidence: float        # Combined confidence score (0.0-1.0)
    signal_scores: dict      # Individual signal contributions
    boundary_type: str       # Primary signal that detected this

    def __repr__(self):
        return f"Boundary(y={self.y_position}, conf={self.confidence:.2f}, type={self.boundary_type})"


class BoundaryDetector:
    """
    Multi-signal boundary detector.

    Analyzes images using multiple signals to find robust panel boundaries.
    """

    def __init__(self, config: dict):
        """
        Initialize detector with configuration.

        Args:
            config: Configuration dictionary from panel_splitting.yaml
        """
        self.config = config
        self.signals_config = config.get('signals', {})
        self.processing_config = config.get('processing', {})

        # Extract signal weights
        self.weights = {
            'whitespace': self.signals_config.get('whitespace', {}).get('weight', 0.4),
            'border_lines': self.signals_config.get('border_lines', {}).get('weight', 0.3),
            'content_breaks': self.signals_config.get('content_breaks', {}).get('weight', 0.2),
            'color_shifts': self.signals_config.get('color_shifts', {}).get('weight', 0.1),
        }

    def detect_boundaries(self, image: np.ndarray) -> List[Boundary]:
        """
        Detect panel boundaries using all enabled signals.

        Args:
            image: Input image (H, W, 3) BGR format

        Returns:
            List of detected boundaries sorted by y_position
        """
        height, width = image.shape[:2]

        # Collect candidates from each signal
        candidates = {}

        # Signal 1: Whitespace gaps
        if self.signals_config.get('whitespace', {}).get('enabled', True):
            ws_candidates = self._detect_whitespace(image)
            for y, score in ws_candidates:
                if y not in candidates:
                    candidates[y] = {'whitespace': 0, 'border_lines': 0, 'content_breaks': 0, 'color_shifts': 0}
                candidates[y]['whitespace'] = score

        # Signal 2: Border lines
        if self.signals_config.get('border_lines', {}).get('enabled', True):
            bl_candidates = self._detect_border_lines(image)
            for y, score in bl_candidates:
                if y not in candidates:
                    candidates[y] = {'whitespace': 0, 'border_lines': 0, 'content_breaks': 0, 'color_shifts': 0}
                candidates[y]['border_lines'] = score

        # Signal 3: Content breaks
        if self.signals_config.get('content_breaks', {}).get('enabled', True):
            cb_candidates = self._detect_content_breaks(image)
            for y, score in cb_candidates:
                if y not in candidates:
                    candidates[y] = {'whitespace': 0, 'border_lines': 0, 'content_breaks': 0, 'color_shifts': 0}
                candidates[y]['content_breaks'] = score

        # Signal 4: Color shifts
        if self.signals_config.get('color_shifts', {}).get('enabled', True):
            cs_candidates = self._detect_color_shifts(image)
            for y, score in cs_candidates:
                if y not in candidates:
                    candidates[y] = {'whitespace': 0, 'border_lines': 0, 'content_breaks': 0, 'color_shifts': 0}
                candidates[y]['color_shifts'] = score

        # Combine scores and create Boundary objects
        boundaries = []
        for y, scores in candidates.items():
            # Use MAX signal as base confidence (strong signal = high confidence)
            # rather than weighted average (which penalizes single-signal detections)
            max_signal_score = max(scores.values())

            # Count how many signals agree (detected this boundary)
            num_signals = sum(1 for score in scores.values() if score > 0.1)

            # Bonus for multiple signals agreeing (up to +0.2)
            agreement_bonus = min(0.2, (num_signals - 1) * 0.1)

            # Final confidence = max signal + agreement bonus
            confidence = min(1.0, max_signal_score + agreement_bonus)

            # Determine primary boundary type (highest score)
            primary_type = max(scores.items(), key=lambda x: x[1])[0]

            boundaries.append(Boundary(
                y_position=y,
                confidence=confidence,
                signal_scores=scores.copy(),
                boundary_type=primary_type
            ))

        # Sort by position
        boundaries.sort(key=lambda b: b.y_position)

        # Merge nearby boundaries (within 100px)
        boundaries = self._merge_nearby_boundaries(boundaries, merge_distance=100)

        return boundaries

    def _merge_nearby_boundaries(self, boundaries: List[Boundary], merge_distance: int = 100) -> List[Boundary]:
        """
        Merge boundaries that are very close together.

        Args:
            boundaries: List of boundaries sorted by position
            merge_distance: Max distance to merge (pixels)

        Returns:
            Merged list of boundaries
        """
        if len(boundaries) <= 1:
            return boundaries

        merged = []
        current = boundaries[0]

        for next_boundary in boundaries[1:]:
            distance = next_boundary.y_position - current.y_position

            if distance <= merge_distance:
                # Merge: take position with higher confidence, combine scores
                if next_boundary.confidence > current.confidence:
                    y_pos = next_boundary.y_position
                else:
                    y_pos = current.y_position

                # Combine signal scores (take max of each)
                combined_scores = {}
                for signal in current.signal_scores.keys():
                    combined_scores[signal] = max(
                        current.signal_scores[signal],
                        next_boundary.signal_scores[signal]
                    )

                # Recalculate confidence
                max_signal_score = max(combined_scores.values())
                num_signals = sum(1 for score in combined_scores.values() if score > 0.1)
                agreement_bonus = min(0.2, (num_signals - 1) * 0.1)
                confidence = min(1.0, max_signal_score + agreement_bonus)

                primary_type = max(combined_scores.items(), key=lambda x: x[1])[0]

                current = Boundary(
                    y_position=y_pos,
                    confidence=confidence,
                    signal_scores=combined_scores,
                    boundary_type=primary_type
                )
            else:
                # Too far apart, keep current and move to next
                merged.append(current)
                current = next_boundary

        # Add the last one
        merged.append(current)

        return merged

    def _detect_whitespace(self, image: np.ndarray) -> List[Tuple[int, float]]:
        """
        Detect boundaries based on white gaps.

        Args:
            image: Input image

        Returns:
            List of (y_position, score) tuples
        """
        height, width = image.shape[:2]
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Get config
        ws_config = self.signals_config.get('whitespace', {})
        white_threshold = ws_config.get('brightness', 245)
        white_percent_threshold = ws_config.get('threshold', 0.90)
        min_gap = self.config.get('panel', {}).get('min_gap_size', 30)

        # Calculate brightness per row
        row_brightness = np.mean(gray, axis=1)

        # Find rows where most pixels are white
        white_pixel_count = np.sum(gray > white_threshold, axis=1)
        white_percent = white_pixel_count / width
        is_white_row = white_percent >= white_percent_threshold

        # Find gaps (consecutive white rows)
        candidates = []
        in_gap = False
        gap_start = 0

        for y in range(height):
            if is_white_row[y]:
                if not in_gap:
                    gap_start = y
                    in_gap = True
            else:
                if in_gap:
                    gap_end = y
                    gap_size = gap_end - gap_start

                    if gap_size >= min_gap:
                        # Score based on gap size (larger = higher confidence)
                        score = min(1.0, gap_size / 200.0)  # Max score at 200px
                        middle = (gap_start + gap_end) // 2
                        candidates.append((middle, score))

                    in_gap = False

        return candidates

    def _detect_border_lines(self, image: np.ndarray) -> List[Tuple[int, float]]:
        """
        Detect horizontal border lines.

        Args:
            image: Input image

        Returns:
            List of (y_position, score) tuples
        """
        height, width = image.shape[:2]
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Get config
        bl_config = self.signals_config.get('border_lines', {})
        min_length_percent = bl_config.get('min_length', 0.95)
        min_length = int(width * min_length_percent)

        # Detect edges
        edge_config = self.processing_config.get('edge_detection', {})
        canny_low = edge_config.get('canny_low', 30)
        canny_high = edge_config.get('canny_high', 100)
        edges = cv2.Canny(gray, canny_low, canny_high)

        # Count horizontal edges per row
        horizontal_edge_count = np.sum(edges, axis=1) / 255  # Divide by 255 since edges are binary

        candidates = []
        for y in range(height):
            if horizontal_edge_count[y] >= min_length * 0.8:  # Allow some tolerance
                # Score based on how complete the line is
                score = min(1.0, horizontal_edge_count[y] / min_length)
                candidates.append((y, score))

        # Merge nearby candidates (within 5 pixels)
        merged = []
        if candidates:
            current_y, current_score = candidates[0]
            current_count = 1

            for y, score in candidates[1:]:
                if y - current_y <= 5:
                    # Merge: average position and max score
                    current_y = (current_y * current_count + y) // (current_count + 1)
                    current_score = max(current_score, score)
                    current_count += 1
                else:
                    merged.append((current_y, current_score))
                    current_y, current_score = y, score
                    current_count = 1

            merged.append((current_y, current_score))

        return merged

    def _detect_content_breaks(self, image: np.ndarray) -> List[Tuple[int, float]]:
        """
        Detect sudden changes in content density.

        Args:
            image: Input image

        Returns:
            List of (y_position, score) tuples
        """
        height, width = image.shape[:2]
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Get config
        cb_config = self.signals_config.get('content_breaks', {})
        threshold = cb_config.get('threshold', 0.70)
        window_size = cb_config.get('window_size', 50)

        # Calculate content density per row (inverse of brightness)
        # More content = lower brightness on average
        row_brightness = np.mean(gray, axis=1)
        content_density = 255 - row_brightness  # Invert so high = more content

        # Smooth to reduce noise
        kernel_size = 10
        kernel = np.ones(kernel_size) / kernel_size
        smoothed_density = np.convolve(content_density, kernel, mode='same')

        candidates = []
        for y in range(window_size, height - window_size):
            # Compare density above vs below
            density_above = np.mean(smoothed_density[y-window_size:y])
            density_below = np.mean(smoothed_density[y:y+window_size])

            # Check for significant drop
            if density_above > 0:
                change = (density_above - density_below) / density_above
                if change >= threshold:
                    score = min(1.0, change)
                    candidates.append((y, score))

        # Merge nearby candidates
        merged = []
        if candidates:
            current_y, current_score = candidates[0]

            for y, score in candidates[1:]:
                if y - current_y <= 20:
                    # Keep the one with higher score
                    if score > current_score:
                        current_y, current_score = y, score
                else:
                    merged.append((current_y, current_score))
                    current_y, current_score = y, score

            merged.append((current_y, current_score))

        return merged

    def _detect_color_shifts(self, image: np.ndarray) -> List[Tuple[int, float]]:
        """
        Detect major color palette changes.

        Args:
            image: Input image

        Returns:
            List of (y_position, score) tuples
        """
        height, width = image.shape[:2]

        # Get config
        cs_config = self.signals_config.get('color_shifts', {})
        threshold = cs_config.get('threshold', 0.60)
        window_size = cs_config.get('window_size', 200)

        candidates = []

        # Sample at intervals to avoid processing every row (performance)
        sample_interval = 20
        for y in range(window_size, height - window_size, sample_interval):
            # Extract windows above and below
            window_above = image[max(0, y-window_size):y, :]
            window_below = image[y:min(height, y+window_size), :]

            if window_above.size == 0 or window_below.size == 0:
                continue

            # Calculate average color for each window
            avg_color_above = np.mean(window_above, axis=(0, 1))
            avg_color_below = np.mean(window_below, axis=(0, 1))

            # Calculate color difference (normalized)
            color_diff = np.linalg.norm(avg_color_above - avg_color_below)
            max_diff = np.sqrt(3 * 255**2)  # Maximum possible difference
            normalized_diff = color_diff / max_diff

            if normalized_diff >= (1.0 - threshold):
                score = min(1.0, normalized_diff)
                candidates.append((y, score))

        return candidates
