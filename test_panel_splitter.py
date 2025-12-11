"""
Test script for the new panel splitter.

Tests multi-signal detection on a sample episode.
"""

import sys
from pathlib import Path

# Add to path
sys.path.insert(0, str(Path(__file__).parent))

from scraper.core.panel_splitter import PanelSplitter


def main():
    print("=" * 70)
    print("PANEL SPLITTER TEST")
    print("=" * 70)
    print()

    # Initialize splitter
    print("📦 Initializing panel splitter...")
    splitter = PanelSplitter()
    print("✅ Loaded configuration")
    print()

    # Test image
    test_image = "data/stitched/ep000/stitched.jpg"
    print(f"🖼️  Test image: {test_image}")
    print()

    # Split episode
    print("🔍 Detecting panels...")
    try:
        panels = splitter.split_episode(test_image)
        print(f"✅ Detected {len(panels)} panels")
        print()

        # Display results
        print("PANEL DETAILS:")
        print("-" * 70)
        for panel in panels:
            print(f"Panel {panel.panel_number:3d}: "
                  f"y={panel.y_start:5d}-{panel.y_end:5d} "
                  f"h={panel.height:4d}px "
                  f"conf={panel.confidence:.2f} "
                  f"type={panel.boundary_type:15s} "
                  f"overlap=({panel.overlap_top},{panel.overlap_bottom}) "
                  f"flags={panel.flags}")

        print()
        print("-" * 70)

        # Statistics
        avg_height = sum(p.height for p in panels) / len(panels)
        avg_confidence = sum(p.confidence for p in panels) / len(panels)
        flagged = sum(1 for p in panels if p.flags)

        print()
        print("STATISTICS:")
        print(f"  Total panels: {len(panels)}")
        print(f"  Average height: {avg_height:.1f}px")
        print(f"  Average confidence: {avg_confidence:.2f}")
        print(f"  Flagged panels: {flagged}")
        print()

        # Test extraction
        print("💾 Testing panel extraction...")
        output_dir = "data/panels_test/ep000"
        metadata = splitter.extract_panels(
            test_image,
            output_dir,
            "s2_ep000_p{:03d}.jpg"
        )
        print(f"✅ Extracted {len(metadata)} panels to {output_dir}")
        print()

        print("=" * 70)
        print("✅ TEST COMPLETE")
        print("=" * 70)

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
