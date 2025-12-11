"""
Debug script to see what signals are detecting.
"""

import sys
from pathlib import Path
import cv2

sys.path.insert(0, str(Path(__file__).parent))

from scraper.core.detectors.boundary_detector import BoundaryDetector
from scraper.core.detectors.content_analyzer import ContentAnalyzer
import yaml


def main():
    # Load config
    config_path = Path('config/panel_splitting.yaml')
    with open(config_path) as f:
        config = yaml.safe_load(f)

    # Load image
    test_image = "data/stitched/ep000/stitched.jpg"
    image = cv2.imread(test_image)
    print(f"Image: {image.shape[1]}x{image.shape[0]}")
    print()

    # Initialize detector
    detector = BoundaryDetector(config)
    analyzer = ContentAnalyzer(config)

    # Test each signal independently
    print("=" * 70)
    print("WHITESPACE DETECTION")
    print("=" * 70)
    ws_candidates = detector._detect_whitespace(image)
    print(f"Found {len(ws_candidates)} whitespace candidates:")
    for y, score in ws_candidates[:20]:
        print(f"  y={y:5d} score={score:.2f}")
    print()

    print("=" * 70)
    print("BORDER LINES DETECTION")
    print("=" * 70)
    bl_candidates = detector._detect_border_lines(image)
    print(f"Found {len(bl_candidates)} border line candidates:")
    for y, score in bl_candidates[:20]:
        print(f"  y={y:5d} score={score:.2f}")
    print()

    print("=" * 70)
    print("CONTENT BREAKS DETECTION")
    print("=" * 70)
    cb_candidates = detector._detect_content_breaks(image)
    print(f"Found {len(cb_candidates)} content break candidates:")
    for y, score in cb_candidates[:20]:
        print(f"  y={y:5d} score={score:.2f}")
    print()

    print("=" * 70)
    print("COLOR SHIFTS DETECTION")
    print("=" * 70)
    cs_candidates = detector._detect_color_shifts(image)
    print(f"Found {len(cs_candidates)} color shift candidates:")
    for y, score in cs_candidates[:20]:
        print(f"  y={y:5d} score={score:.2f}")
    print()

    print("=" * 70)
    print("COMBINED DETECTION")
    print("=" * 70)
    boundaries = detector.detect_boundaries(image)
    print(f"Found {len(boundaries)} combined boundaries:")
    for b in boundaries[:20]:
        print(f"  y={b.y_position:5d} conf={b.confidence:.2f} type={b.boundary_type:15s} "
              f"ws={b.signal_scores['whitespace']:.2f} "
              f"bl={b.signal_scores['border_lines']:.2f} "
              f"cb={b.signal_scores['content_breaks']:.2f} "
              f"cs={b.signal_scores['color_shifts']:.2f}")
    print()

    # Compare with original splits
    print("=" * 70)
    print("COMPARISON WITH ORIGINAL SPLITS")
    print("=" * 70)
    import json
    data = json.load(open('data/panel_metadata.json'))
    ep0_panels = [p for p in data['panels'] if p['season']==2 and p['episode']==0]
    original_splits = [p['position_in_stitched']['y_start'] for p in ep0_panels[1:]]

    print(f"Original system found splits at: {len(original_splits)} positions")
    print(f"New system found: {len(boundaries)} positions")
    print()

    # Check how close we are
    for orig_y in original_splits[:15]:
        closest = min(boundaries, key=lambda b: abs(b.y_position - orig_y)) if boundaries else None
        if closest:
            distance = abs(closest.y_position - orig_y)
            print(f"Original split at y={orig_y:5d} -> Closest detection: y={closest.y_position:5d} (distance={distance:4d}px, conf={closest.confidence:.2f})")
        else:
            print(f"Original split at y={orig_y:5d} -> NO DETECTION")


if __name__ == "__main__":
    main()
