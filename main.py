"""
Hand Jumper Webtoon Database Manager
Main UI to manage all scraper and processing scripts
"""

import subprocess
import sys
from pathlib import Path
import json
from datetime import datetime
import os

# Script paths
SCRAPER_DIR = Path("scraper")
DATA_DIR = Path("data")

SCRIPTS = {
    '1': {
        'name': 'Scrape Webtoon Episodes',
        'script': SCRAPER_DIR / 'scraper.py',
        'description': 'Download all episodes from webtoons.com (resumes interrupted downloads)',
        'output': DATA_DIR / 'originals',
        'metadata': DATA_DIR / 'episode_metadata.json'
    },
    '2': {
        'name': 'Scrape Wiki Data',
        'script': SCRAPER_DIR / 'scrape_wiki.py',
        'description': 'Extract characters, locations, organizations from wiki',
        'output': DATA_DIR / 'wiki_categories.json',
        'metadata': DATA_DIR / 'wiki_categories.json'
    },
    '3': {
        'name': 'Stitch and Extract Panels',
        'script': SCRAPER_DIR / 'stitch_and_extract.py',
        'description': 'Stitch episode images and extract individual panels',
        'output': DATA_DIR / 'panels_original',
        'metadata': DATA_DIR / 'panel_metadata.json'
    },
    '4': {
        'name': 'Optimize Images',
        'script': SCRAPER_DIR / 'optimize_images.py',
        'description': 'Create web-optimized versions of panels (~200KB each)',
        'output': DATA_DIR / 'panels_web',
        'metadata': DATA_DIR / 'optimization_metadata.json'
    },
    '5': {
        'name': 'Build Database',
        'script': SCRAPER_DIR / 'build_database.py',
        'description': 'Combine all data into final JSON database',
        'output': Path('frontend/data'),
        'metadata': Path('frontend/data/panels_database.json')
    }
}


def clear_screen():
    """Clear the terminal screen"""
    os.system('cls' if os.name == 'nt' else 'clear')


def print_header():
    """Print the main header"""
    print("=" * 70)
    print(" " * 15 + "HAND JUMPER WEBTOON DATABASE MANAGER")
    print("=" * 70)
    print()


def check_status(script_info):
    """Check if a script has been run and get status info"""
    status = {
        'output_exists': False,
        'metadata_exists': False,
        'item_count': 0,
        'last_modified': None
    }

    # Check output directory/file
    output_path = Path(script_info['output'])
    if output_path.exists():
        status['output_exists'] = True

        # Count items
        if output_path.is_dir():
            # Count subdirectories or files
            items = list(output_path.rglob('*'))
            status['item_count'] = len([i for i in items if i.is_file()])
        else:
            status['item_count'] = 1

    # Check metadata file
    metadata_path = Path(script_info['metadata'])
    if metadata_path.exists():
        status['metadata_exists'] = True

        # Get last modified time
        mtime = metadata_path.stat().st_mtime
        status['last_modified'] = datetime.fromtimestamp(mtime)

        # Try to read metadata for more info
        try:
            with open(metadata_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

                # Extract useful counts from different metadata formats
                if 'total_episodes' in data:
                    # For episode metadata, count unique episodes not total entries
                    if 'episodes' in data and isinstance(data['episodes'], list):
                        # Count unique (season, episode) tuples
                        unique_eps = set()
                        for ep in data['episodes']:
                            if isinstance(ep, dict) and 'season' in ep and 'episode' in ep:
                                unique_eps.add((ep['season'], ep['episode']))
                        status['item_count'] = len(unique_eps) if unique_eps else data['total_episodes']
                    else:
                        status['item_count'] = data['total_episodes']
                elif 'total_panels' in data:
                    status['item_count'] = data['total_panels']
                elif 'total_images' in data:
                    status['item_count'] = data['total_images']
                elif 'total_entries' in data:
                    status['item_count'] = data['total_entries']
                elif 'panels' in data:
                    status['item_count'] = len(data['panels'])
        except Exception as e:
            # Failed to read metadata, but that's okay
            pass

    return status


def get_status_symbol(status, script_key):
    """Get a symbol representing the status with validation"""
    # Validation rules for each step
    validation_rules = {
        '1': {'min_items': 50, 'name': 'episodes'},  # Should have at least 50 episodes
        '2': {'min_items': 10, 'name': 'wiki entries'},  # Should have wiki data
        '3': {'min_items': 100, 'name': 'panels'},  # Should have lots of panels
        '4': {'min_items': 100, 'name': 'optimized images'},  # Should match panels
        '5': {'min_items': 100, 'name': 'database entries'}  # Should have full database
    }

    if not status['output_exists']:
        return '[NOT RUN]'

    # Check if we have metadata and minimum item count
    if status['metadata_exists']:
        rule = validation_rules.get(script_key, {})
        min_items = rule.get('min_items', 0)

        if status['item_count'] >= min_items:
            return '[DONE]'
        else:
            return '[INCOMPLETE]'

    return '[PARTIAL]'


def print_menu():
    """Print the main menu with status"""
    print_header()
    print("PIPELINE STATUS:")
    print("-" * 70)

    for key, script_info in SCRIPTS.items():
        status = check_status(script_info)
        symbol = get_status_symbol(status, key)

        # Format status info
        status_info = ""
        if status['metadata_exists']:
            if status['item_count'] > 0:
                status_info = f"({status['item_count']} items)"
            if status['last_modified']:
                date_str = status['last_modified'].strftime('%Y-%m-%d %H:%M')
                status_info += f" - Last: {date_str}"

        print(f"  {key}. {symbol:12} {script_info['name']}")
        print(f"     {script_info['description']}")
        if status_info:
            print(f"     {status_info}")
        print()

    print("-" * 70)
    print()
    print("OPTIONS:")
    print("  [1-5]  Run individual step")
    print("  [A]    Run ALL steps in sequence")
    print("  [S]    Show detailed status")
    print("  [C]    Check requirements")
    print("  [Q]    Quit")
    print()


def show_detailed_status():
    """Show detailed status information"""
    clear_screen()
    print_header()
    print("DETAILED STATUS:")
    print("=" * 70)
    print()

    for key, script_info in SCRIPTS.items():
        status = check_status(script_info)

        print(f"[{key}] {script_info['name']}")
        print(f"    Script: {script_info['script']}")
        print(f"    Output: {script_info['output']}")
        print(f"    Metadata: {script_info['metadata']}")
        print()
        print(f"    Output exists: {'YES' if status['output_exists'] else 'NO'}")
        print(f"    Metadata exists: {'YES' if status['metadata_exists'] else 'NO'}")

        if status['item_count'] > 0:
            print(f"    Items: {status['item_count']}")

        if status['last_modified']:
            print(f"    Last modified: {status['last_modified'].strftime('%Y-%m-%d %H:%M:%S')}")

        print()

    print("=" * 70)
    input("\nPress Enter to return to menu...")


def check_requirements():
    """Check if required Python packages are installed"""
    clear_screen()
    print_header()
    print("CHECKING REQUIREMENTS:")
    print("=" * 70)
    print()

    required_packages = [
        ('httpx', 'HTTP client for scraping'),
        ('asyncio', 'Async support (built-in)'),
        ('bs4', 'BeautifulSoup for HTML parsing'),
        ('cv2', 'OpenCV for image processing'),
        ('PIL', 'Pillow for image optimization'),
        ('numpy', 'Numerical operations'),
        ('tqdm', 'Progress bars'),
        ('json', 'JSON handling (built-in)'),
        ('pathlib', 'Path handling (built-in)')
    ]

    print("Checking installed packages...\n")

    all_installed = True
    for package, description in required_packages:
        try:
            __import__(package)
            print(f"  [OK]      {package:15} - {description}")
        except ImportError:
            print(f"  [MISSING] {package:15} - {description}")
            all_installed = False

    print()
    print("=" * 70)

    if not all_installed:
        print("\nSome packages are missing. Install them with:")
        print("  pip install httpx beautifulsoup4 opencv-python pillow numpy tqdm")
    else:
        print("\nAll required packages are installed!")

    print()
    input("Press Enter to return to menu...")


def run_script(script_info):
    """Run a single script"""
    clear_screen()
    print_header()
    print(f"RUNNING: {script_info['name']}")
    print("=" * 70)
    print(f"Description: {script_info['description']}")
    print(f"Script: {script_info['script']}")
    print()
    print("Starting script... (Press Ctrl+C to cancel)")
    print("-" * 70)
    print()

    try:
        # Run the script and show output in real-time
        result = subprocess.run(
            [sys.executable, str(script_info['script'])],
            cwd=Path.cwd(),
            text=True,
            bufsize=1
        )

        print()
        print("-" * 70)

        if result.returncode == 0:
            print(f"\n[SUCCESS] {script_info['name']} completed successfully!")
        else:
            print(f"\n[ERROR] Script exited with code {result.returncode}")

    except KeyboardInterrupt:
        print("\n\n[CANCELLED] Script interrupted by user")
    except Exception as e:
        print(f"\n[ERROR] Failed to run script: {e}")

    print()
    input("Press Enter to return to menu...")


def run_all_scripts():
    """Run all scripts in sequence"""
    clear_screen()
    print_header()
    print("RUNNING ALL SCRIPTS IN SEQUENCE")
    print("=" * 70)
    print()
    print("This will run all 5 steps in order:")
    for key, script_info in SCRIPTS.items():
        print(f"  {key}. {script_info['name']}")
    print()
    confirm = input("Continue? (y/n): ").strip().lower()

    if confirm != 'y':
        return

    print()
    print("=" * 70)

    start_time = datetime.now()

    for key in sorted(SCRIPTS.keys()):
        script_info = SCRIPTS[key]
        print()
        print(f"[STEP {key}/5] {script_info['name']}")
        print("-" * 70)

        try:
            result = subprocess.run(
                [sys.executable, str(script_info['script'])],
                cwd=Path.cwd(),
                text=True
            )

            if result.returncode != 0:
                print(f"\n[ERROR] Step {key} failed with code {result.returncode}")
                print("Stopping pipeline.")
                break

            print(f"[OK] Step {key} complete")

        except KeyboardInterrupt:
            print("\n\n[CANCELLED] Pipeline interrupted by user")
            break
        except Exception as e:
            print(f"\n[ERROR] Step {key} failed: {e}")
            break

    end_time = datetime.now()
    duration = end_time - start_time

    print()
    print("=" * 70)
    print(f"Pipeline finished in {duration}")
    print()
    input("Press Enter to return to menu...")


def main():
    """Main menu loop"""
    while True:
        clear_screen()
        print_menu()

        choice = input("Select option: ").strip().upper()

        if choice == 'Q':
            print("\nExiting...")
            break

        elif choice == 'S':
            show_detailed_status()

        elif choice == 'C':
            check_requirements()

        elif choice == 'A':
            run_all_scripts()

        elif choice in SCRIPTS:
            run_script(SCRIPTS[choice])

        else:
            print("\nInvalid option. Please try again.")
            input("Press Enter to continue...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nExiting...")
        sys.exit(0)
