"""
Database Builder
Combines panel metadata with automated and manual tags into final JSON database
"""

import json
from pathlib import Path
from datetime import datetime
import sys

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Use absolute paths relative to script location
SCRIPT_DIR = Path(__file__).parent.parent

# Input files
PANEL_METADATA = SCRIPT_DIR / "data" / "panel_metadata.json"
WIKI_CATEGORIES = SCRIPT_DIR / "data" / "wiki_categories.json"
MANUAL_CHARACTER_LIST = SCRIPT_DIR / "data" / "manual_character_list.json"
MANUAL_TAGS_DIR = SCRIPT_DIR / "data" / "manual_tags"

# Output files
OUTPUT_DIR = SCRIPT_DIR / "frontend" / "data"
DATABASE_FILE = OUTPUT_DIR / "panels_database.json"


def load_json(filepath):
    """Load JSON file if it exists and is valid"""
    if not filepath.exists():
        return None

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {filepath}: {e}")
        return None
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return None


def create_database_schema():
    """
    Define the database schema for panels

    Each panel entry contains:
    - id: Unique identifier (e.g., "ep001_p001")
    - episode: Episode number
    - panelNumber: Panel number within episode
    - imagePath: Relative path to web-optimized image
    - originalPath: Path to high-quality original
    - dimensions: Image dimensions
    - automated: Automatically generated tags
    - manual: Manually added tags
    - metadata: Additional metadata
    """

    schema = {
        "version": "1.0",
        "created": datetime.now().isoformat(),
        "description": "Hand Jumper panel database with searchable tags",
        "schema": {
            "panel": {
                "id": "string (unique identifier)",
                "episode": "integer",
                "panelNumber": "integer",
                "imagePath": "string (web-optimized image path)",
                "originalPath": "string (high-quality original path)",
                "dimensions": {
                    "width": "integer",
                    "height": "integer"
                },
                "automated": {
                    "detected": "array (auto-detected features)",
                    "confidence": "object (confidence scores)"
                },
                "manual": {
                    "characters": "array (character names)",
                    "locations": "array (location names)",
                    "organizations": "array (organization names)",
                    "items": "array (items present)",
                    "tags": "array (general tags)",
                    "emotions": "array (emotional tone)",
                    "plotPoints": "array (story significance)",
                    "dialogue": "boolean (has dialogue)",
                    "action": "boolean (action scene)",
                    "notes": "string (additional notes)"
                },
                "metadata": {
                    "filesize": "integer (bytes)",
                    "lastModified": "string (ISO date)",
                    "tagged": "boolean (has manual tags)",
                    "verified": "boolean (tags verified)"
                }
            }
        },
        "panels": []
    }

    return schema


def build_database():
    """Build the complete database from all sources"""
    print("Building Database")
    print("=" * 50)

    # Load panel metadata
    print("Loading panel metadata...")
    panel_data = load_json(PANEL_METADATA)
    if not panel_data:
        print(f"Error: Panel metadata not found or invalid at {PANEL_METADATA}")
        print("Please run panel extraction first (Step 3)")
        return

    if 'panels' not in panel_data or not isinstance(panel_data['panels'], list):
        print("Error: Invalid panel metadata format - missing 'panels' array")
        return

    # Load wiki categories
    print("Loading wiki categories...")
    wiki_data = load_json(WIKI_CATEGORIES)

    # Create database schema
    database = create_database_schema()

    # Process each panel
    panels = panel_data.get('panels', [])
    print(f"Processing {len(panels)} panels...")

    for panel in panels:
        # Extract basic info
        filename = Path(panel['filename']).stem  # e.g., "ep001_p001"

        # Parse episode, panel number from filename (no seasons)
        try:
            parts = filename.split('_')
            if len(parts) < 2 or not parts[0].startswith('ep') or not parts[1].startswith('p'):
                print(f"Warning: Skipping panel with invalid filename format: {filename}")
                continue

            episode = int(parts[0][2:])  # Remove 'ep' prefix
            panel_num = int(parts[1][1:])  # Remove 'p' prefix
        except (ValueError, IndexError) as e:
            print(f"Warning: Could not parse filename '{filename}': {e}")
            continue

        # Create panel entry
        panel_entry = {
            "id": filename,
            "episode": episode,
            "panelNumber": panel_num,
            "imagePath": f"images/ep{episode:03d}/{filename}.jpg",
            "originalPath": panel['path'],
            "dimensions": panel.get('dimensions', {}),
            "automated": {
                "detected": [],
                "confidence": {}
            },
            "manual": {
                "characters": [],
                "locations": [],
                "organizations": [],
                "items": [],
                "tags": [],
                "emotions": [],
                "plotPoints": [],
                "dialogue": False,
                "action": False,
                "notes": ""
            },
            "metadata": {
                "filesize": 0,
                "lastModified": datetime.now().isoformat(),
                "tagged": False,
                "verified": False
            }
        }

        # Check for manual tags
        manual_tag_file = MANUAL_TAGS_DIR / f"{filename}.json"
        if manual_tag_file.exists():
            manual_tags = load_json(manual_tag_file)
            if manual_tags:
                panel_entry['manual'].update(manual_tags)
                panel_entry['metadata']['tagged'] = True

        database['panels'].append(panel_entry)

    # Save main database
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"\nSaving database...")

    # Save complete database
    with open(DATABASE_FILE, 'w', encoding='utf-8') as f:
        json.dump(database, f, indent=2, ensure_ascii=False)
    print(f"Main database: {DATABASE_FILE}")

    # Save wiki categories for frontend
    if wiki_data:
        wiki_output = OUTPUT_DIR / "wiki_data.json"
        with open(wiki_output, 'w', encoding='utf-8') as f:
            json.dump(wiki_data, f, indent=2, ensure_ascii=False)
        print(f"✓ Wiki data: {wiki_output}")

    # Create statistics (no seasons)
    stats = {
        "total_panels": len(database['panels']),
        "total_episodes": len(set(p['episode'] for p in database['panels'])),
        "tagged_panels": sum(1 for p in database['panels'] if p['metadata']['tagged']),
        "last_updated": datetime.now().isoformat()
    }

    stats_file = OUTPUT_DIR / "statistics.json"
    with open(stats_file, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
    print(f"✓ Statistics: {stats_file}")

    print(f"\nDatabase build complete!")
    print(f"Total panels: {stats['total_panels']}")
    print(f"Total episodes: {stats['total_episodes']}")
    print(f"Tagged panels: {stats['tagged_panels']}")


if __name__ == "__main__":
    # Create manual tags directory if it doesn't exist
    MANUAL_TAGS_DIR.mkdir(parents=True, exist_ok=True)

    build_database()
