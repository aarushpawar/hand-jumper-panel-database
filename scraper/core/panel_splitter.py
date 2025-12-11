"""
Main panel splitting orchestrator.

Coordinates multi-signal detection, validation, and extraction
to split webtoon episodes into individual panels.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Dict, Any
import numpy as np
import cv2
import yaml

from .detectors.boundary_detector import BoundaryDetector, Boundary
from .detectors.content_analyzer import ContentAnalyzer
from .detectors.overlap_calculator import OverlapCalculator


@dataclass
class PanelInfo:
    """Information about an extracted panel."""
    panel_number: int
    y_start: int
    y_end: int
    height: int
    width: int
    confidence: float
    boundary_type: str
    overlap_top: int
    overlap_bottom: int
    flags: List[str]


class PanelSplitter:
    """
    Main panel splitting system.

    Combines multiple detection signals, validates boundaries,
    and extracts panels with adaptive overlap.
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize splitter with configuration.

        Args:
            config_path: Path to panel_splitting.yaml, or None for default
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / 'config' / 'panel_splitting.yaml'

        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        # Initialize components
        self.boundary_detector = BoundaryDetector(self.config)
        self.content_analyzer = ContentAnalyzer(self.config)
        self.overlap_calculator = OverlapCalculator(self.config)

        # Extract config values
        self.min_panel_height = self.config.get('panel', {}).get('min_height', 200)
        self.max_panel_height = self.config.get('panel', {}).get('max_height', 4000)
        self.min_confidence = self.config.get('validation', {}).get('min_confidence', 0.50)
        self.quality_config = self.config.get('quality', {})

    def split_episode(self, image_path: str) -> List[PanelInfo]:
        """
        Split an episode image into panels.

        Args:
            image_path: Path to stitched episode image

        Returns:
            List of PanelInfo objects with metadata
        """
        # Load image
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"Failed to load image: {image_path}")

        height, width = image.shape[:2]

        # Step 1: Detect candidate boundaries
        candidates = self.boundary_detector.detect_boundaries(image)

        # Step 2: Validate boundaries
        validated_boundaries = []
        for boundary in candidates:
            if boundary.confidence < self.min_confidence:
                continue

            is_valid, reason = self.content_analyzer.validate_boundary(
                image, boundary.y_position
            )

            if is_valid:
                validated_boundaries.append(boundary)

        # Step 3: Create panels from validated boundaries
        panels = self._create_panels(image, validated_boundaries)

        # Step 4: Quality checks and fixes
        panels = self._apply_quality_checks(panels, height)

        return panels

    def extract_panels(
        self,
        image_path: str,
        output_dir: str,
        filename_template: str = "panel_{:03d}.jpg"
    ) -> List[Dict[str, Any]]:
        """
        Split episode and save panel images.

        Args:
            image_path: Path to stitched episode image
            output_dir: Directory to save panels
            filename_template: Template for panel filenames

        Returns:
            List of panel metadata dictionaries
        """
        # Load image
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"Failed to load image: {image_path}")

        # Get panel info
        panels = self.split_episode(image_path)

        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Extract and save each panel
        metadata = []
        for panel in panels:
            # Extract panel region
            panel_img = image[panel.y_start:panel.y_end, :]

            # Generate filename
            filename = filename_template.format(panel.panel_number)
            output_file = output_path / filename

            # Save image
            cv2.imwrite(str(output_file), panel_img)

            # Create metadata
            metadata.append({
                'filename': filename,
                'path': str(output_file),
                'panel_number': panel.panel_number,
                'dimensions': {
                    'width': panel.width,
                    'height': panel.height
                },
                'position_in_stitched': {
                    'y_start': panel.y_start,
                    'y_end': panel.y_end
                },
                'detection_metadata': {
                    'confidence': panel.confidence,
                    'boundary_type': panel.boundary_type,
                    'overlap_top': panel.overlap_top,
                    'overlap_bottom': panel.overlap_bottom,
                    'flags': panel.flags
                }
            })

        return metadata

    def _create_panels(
        self,
        image: np.ndarray,
        boundaries: List[Boundary]
    ) -> List[PanelInfo]:
        """
        Create panel info from validated boundaries.

        Args:
            image: Input image
            boundaries: List of validated boundaries

        Returns:
            List of PanelInfo objects
        """
        height, width = image.shape[:2]
        panels = []

        # Sort boundaries by position
        boundaries.sort(key=lambda b: b.y_position)

        # Extract boundary positions
        boundary_positions = [b.y_position for b in boundaries]

        # Create panels between boundaries
        for i in range(len(boundary_positions) + 1):
            # Determine base bounds
            if i == 0:
                y_start = 0
                boundary_above = None
            else:
                y_start = boundary_positions[i - 1]
                boundary_above = boundaries[i - 1]

            if i >= len(boundary_positions):
                y_end = height
                boundary_below = None
            else:
                y_end = boundary_positions[i]
                boundary_below = boundaries[i]

            # Calculate overlap
            overlap_top = 0
            overlap_bottom = 0

            if boundary_above is not None:
                _, overlap_top = self.overlap_calculator.calculate_overlap(
                    image, boundary_above.y_position, boundary_above.confidence, 'bottom'
                )

            if boundary_below is not None:
                _, overlap_bottom = self.overlap_calculator.calculate_overlap(
                    image, boundary_below.y_position, boundary_below.confidence, 'top'
                )

            # Apply overlap
            y_start_with_overlap = max(0, y_start - overlap_top)
            y_end_with_overlap = min(height, y_end + overlap_bottom)

            panel_height = y_end_with_overlap - y_start_with_overlap

            # Get confidence from the boundary below (or 1.0 if it's the last panel)
            confidence = boundary_below.confidence if boundary_below else 1.0
            boundary_type = boundary_below.boundary_type if boundary_below else 'end_of_image'

            panels.append(PanelInfo(
                panel_number=i + 1,
                y_start=y_start_with_overlap,
                y_end=y_end_with_overlap,
                height=panel_height,
                width=width,
                confidence=confidence,
                boundary_type=boundary_type,
                overlap_top=overlap_top,
                overlap_bottom=overlap_bottom,
                flags=[]
            ))

        return panels

    def _apply_quality_checks(
        self,
        panels: List[PanelInfo],
        image_height: int
    ) -> List[PanelInfo]:
        """
        Apply quality checks and auto-fix issues.

        Args:
            panels: List of panel info
            image_height: Total image height

        Returns:
            Updated list of panels
        """
        auto_fix = self.quality_config.get('auto_fix', True)
        flag_threshold = self.quality_config.get('flag_threshold', 0.3)
        merge_tiny = self.quality_config.get('merge_tiny', 150)
        force_split_at = self.quality_config.get('force_split_at', 4000)

        # Flag low confidence panels
        for panel in panels:
            if panel.confidence < flag_threshold:
                panel.flags.append('low_confidence')

        # Flag/fix tiny panels
        if auto_fix:
            panels = self._merge_tiny_panels(panels, merge_tiny)
        else:
            for panel in panels:
                if panel.height < merge_tiny:
                    panel.flags.append('too_short')

        # Flag/fix huge panels
        if auto_fix:
            panels = self._split_huge_panels(panels, force_split_at, image_height)
        else:
            for panel in panels:
                if panel.height > force_split_at:
                    panel.flags.append('too_tall')

        # Renumber panels after modifications
        for i, panel in enumerate(panels):
            panel.panel_number = i + 1

        return panels

    def _merge_tiny_panels(
        self,
        panels: List[PanelInfo],
        min_height: int
    ) -> List[PanelInfo]:
        """
        Merge panels that are too short.

        Args:
            panels: List of panels
            min_height: Minimum acceptable height

        Returns:
            Updated list with tiny panels merged
        """
        if len(panels) <= 1:
            return panels

        merged = []
        i = 0

        while i < len(panels):
            current = panels[i]

            if current.height < min_height and i < len(panels) - 1:
                # Merge with next panel
                next_panel = panels[i + 1]
                merged_panel = PanelInfo(
                    panel_number=current.panel_number,
                    y_start=current.y_start,
                    y_end=next_panel.y_end,
                    height=next_panel.y_end - current.y_start,
                    width=current.width,
                    confidence=min(current.confidence, next_panel.confidence),
                    boundary_type='merged',
                    overlap_top=current.overlap_top,
                    overlap_bottom=next_panel.overlap_bottom,
                    flags=['merged_tiny']
                )
                merged.append(merged_panel)
                i += 2  # Skip next panel
            else:
                merged.append(current)
                i += 1

        return merged

    def _split_huge_panels(
        self,
        panels: List[PanelInfo],
        max_height: int,
        image_height: int
    ) -> List[PanelInfo]:
        """
        Force-split panels that are too tall.

        Args:
            panels: List of panels
            max_height: Maximum acceptable height
            image_height: Total image height

        Returns:
            Updated list with huge panels split
        """
        result = []

        for panel in panels:
            if panel.height <= max_height:
                result.append(panel)
            else:
                # Split into chunks
                num_chunks = (panel.height + max_height - 1) // max_height
                chunk_size = panel.height // num_chunks

                for chunk_idx in range(num_chunks):
                    chunk_start = panel.y_start + (chunk_idx * chunk_size)
                    chunk_end = panel.y_start + ((chunk_idx + 1) * chunk_size)

                    if chunk_idx == num_chunks - 1:
                        chunk_end = panel.y_end  # Last chunk goes to the end

                    result.append(PanelInfo(
                        panel_number=panel.panel_number,
                        y_start=chunk_start,
                        y_end=chunk_end,
                        height=chunk_end - chunk_start,
                        width=panel.width,
                        confidence=0.5,  # Lower confidence for forced splits
                        boundary_type='forced_split',
                        overlap_top=panel.overlap_top if chunk_idx == 0 else 100,
                        overlap_bottom=panel.overlap_bottom if chunk_idx == num_chunks - 1 else 100,
                        flags=['forced_split']
                    ))

        return result
