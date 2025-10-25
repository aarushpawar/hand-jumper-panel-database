"""
Smart Hand Jumper Scraper
- Fetches all episodes from the series
- Only downloads missing images (resumes interrupted downloads)
- Checks existing folders and fills gaps
- Can be run multiple times safely
"""

import httpx
import asyncio
from pathlib import Path
import json
from bs4 import BeautifulSoup
import time
import sys
import re

sys.stdout.reconfigure(line_buffering=True)

# Configuration
# Hand Jumper series on Webtoon
TITLE_NO = "2702"
BASE_URL = "https://www.webtoons.com/en/thriller/hand-jumper"
EPISODE_LIST_URL = f"{BASE_URL}/list?title_no={TITLE_NO}"

# User agent for web requests (identifies as a standard browser)
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'

# Use absolute paths relative to script location
SCRIPT_DIR = Path(__file__).parent.parent
OUTPUT_DIR = SCRIPT_DIR / "data" / "originals"
METADATA_FILE = SCRIPT_DIR / "data" / "episode_metadata.json"

# Settings
CONCURRENT_EPISODES = 2  # Download 2 episodes at once
DELAY_BETWEEN_REQUESTS = 1.5
MAX_RETRIES = 3

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def parse_episode_title(title):
    """
    Extract season and episode number from episode title.

    Args:
        title: Episode title string (e.g., "Ep. 1 - First Day")

    Returns:
        tuple: (season, episode) integers
    """
    season = 2  # Default
    episode = 0

    if '(S1)' in title or 'S1' in title or 'Season 1' in title:
        season = 1
    elif '(S2)' in title or 'S2' in title or 'Season 2' in title:
        season = 2

    ep_match = re.search(r'Ep\.?\s*(\d+)', title, re.IGNORECASE)
    if ep_match:
        episode = int(ep_match.group(1))
    else:
        num_match = re.search(r'(\d+)', title)
        if num_match:
            episode = int(num_match.group(1))

    return season, episode


def get_existing_episodes():
    """
    Scan existing directories to find downloaded episodes.

    Returns:
        dict: Nested dict of {season: {episode: {path, image_count, images}}}
    """
    existing = {}

    if not OUTPUT_DIR.exists():
        return existing

    for season_dir in OUTPUT_DIR.iterdir():
        if not season_dir.is_dir() or not season_dir.name.startswith('s'):
            continue

        season_num = int(season_dir.name[1:])

        for ep_dir in season_dir.iterdir():
            if not ep_dir.is_dir() or not ep_dir.name.startswith('ep'):
                continue

            ep_num = int(ep_dir.name.replace('ep', ''))

            # Count existing images
            images = list(ep_dir.glob('page_*.jpg'))

            if season_num not in existing:
                existing[season_num] = {}

            existing[season_num][ep_num] = {
                'path': ep_dir,
                'image_count': len(images),
                'images': sorted([img.name for img in images])
            }

    return existing


async def get_all_episodes(client):
    """
    Fetch complete list of all episodes from Webtoon.

    Args:
        client: httpx.AsyncClient for making requests

    Returns:
        list: List of episode dicts with url, title, season, episode
    """
    print("Fetching complete episode list...", flush=True)
    episodes = []
    seen_urls = set()  # Track URLs to avoid duplicates
    page = 1
    max_pages = 20  # Safety limit

    while page <= max_pages:
        url = f"{EPISODE_LIST_URL}&page={page}"

        try:
            response = await client.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            # Find episode list items (each <li> is one episode)
            episode_items = soup.select('#_listUl li')

            if not episode_items:
                print(f"  Page {page}: No more episodes found, stopping", flush=True)
                break

            new_episodes_this_page = 0

            for item in episode_items:
                # Get the main link (first <a> in the item)
                link = item.select_one('a')
                if not link:
                    continue

                episode_url = link.get('href')
                if not episode_url or not ('/episode/' in episode_url or '/viewer?' in episode_url):
                    continue

                # Skip if we've already seen this URL
                if episode_url in seen_urls:
                    continue

                seen_urls.add(episode_url)

                # Get title
                title_elem = link.select_one('.subj span')
                title = title_elem.text.strip() if title_elem else ""

                # Skip if no title
                if not title:
                    continue

                full_url = f"https://www.webtoons.com{episode_url}" if episode_url.startswith('/') else episode_url

                season, ep_num = parse_episode_title(title)

                episodes.append({
                    'url': full_url,
                    'title': title,
                    'season': season,
                    'episode': ep_num
                })
                new_episodes_this_page += 1

            print(f"  Page {page}: Found {new_episodes_this_page} unique episodes (total: {len(episodes)})", flush=True)

            # If we found no new episodes, we've probably reached the end
            if new_episodes_this_page == 0:
                print(f"  No new episodes on page {page}, stopping", flush=True)
                break

            page += 1
            await asyncio.sleep(DELAY_BETWEEN_REQUESTS)

        except Exception as e:
            print(f"[ERROR] Page {page}: {e}", flush=True)
            break

    # Remove any duplicate episodes based on (season, episode) tuple
    unique_episodes = {}
    for ep in episodes:
        key = (ep['season'], ep['episode'])
        if key not in unique_episodes:
            unique_episodes[key] = ep

    final_episodes = list(unique_episodes.values())
    final_episodes.sort(key=lambda x: (x['season'], x['episode']))

    print(f"\n[OK] Total unique episodes found: {len(final_episodes)}", flush=True)
    return final_episodes


async def download_episode_images(client, episode, existing_data, semaphore):
    """
    Download images for one episode, with resume capability.

    Args:
        client: httpx.AsyncClient for downloads
        episode: Episode dict with url, title, season, episode
        existing_data: Dict of already downloaded episodes
        semaphore: asyncio.Semaphore for rate limiting

    Returns:
        dict: Download result with status and counts
    """
    async with semaphore:
        season = episode['season']
        ep_num = episode['episode']

        # Check if we already have this episode
        existing_images = []
        expected_count = None

        if season in existing_data and ep_num in existing_data[season]:
            existing_images = existing_data[season][ep_num]['images']
            print(f"\n[S{season} E{ep_num}] Found {len(existing_images)} existing images", flush=True)
        else:
            print(f"\n[S{season} E{ep_num}] New episode - {episode['title']}", flush=True)

        try:
            # Fetch episode page to see how many images there should be
            response = await client.get(episode['url'])
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            viewer = soup.select_one('#_imageList')
            if not viewer:
                print(f"  [WARNING] No viewer found", flush=True)
                return None

            image_urls = []
            for img in viewer.select('img'):
                img_url = img.get('data-url') or img.get('src')
                if img_url:
                    image_urls.append(img_url)

            if not image_urls:
                print(f"  [WARNING] No images found", flush=True)
                return None

            total_images = len(image_urls)
            existing_count = len(existing_images)

            # Check if complete
            if existing_count == total_images:
                print(f"  [OK] Already complete ({total_images} images)", flush=True)
                return {
                    'season': season,
                    'episode': ep_num,
                    'title': episode['title'],
                    'url': episode['url'],
                    'image_count': total_images,
                    'status': 'already_complete'
                }

            # Download missing images
            print(f"  Need to download: {total_images - existing_count} images (have {existing_count}/{total_images})", flush=True)

            ep_dir = OUTPUT_DIR / f"s{season}" / f"ep{ep_num:03d}"
            ep_dir.mkdir(parents=True, exist_ok=True)

            downloaded_count = 0
            for idx, img_url in enumerate(image_urls, 1):
                img_filename = f"page_{idx:03d}.jpg"
                img_path = ep_dir / img_filename

                # Skip if exists
                if img_path.exists():
                    continue

                # Download with retries
                for attempt in range(MAX_RETRIES):
                    try:
                        headers = {
                            'Referer': 'https://www.webtoons.com/',
                            'User-Agent': USER_AGENT
                        }
                        img_response = await client.get(img_url, headers=headers, timeout=30.0)
                        img_response.raise_for_status()

                        img_path.write_bytes(img_response.content)
                        downloaded_count += 1

                        if downloaded_count % 20 == 0:
                            print(f"    Downloaded {downloaded_count} new images...", flush=True)

                        break
                    except Exception as e:
                        if attempt == MAX_RETRIES - 1:
                            print(f"    [ERROR] Image {idx} failed: {e}", flush=True)
                        else:
                            await asyncio.sleep(2 ** attempt)

                await asyncio.sleep(0.3)

            print(f"  [OK] Downloaded {downloaded_count} new images (total: {total_images})", flush=True)

            return {
                'season': season,
                'episode': ep_num,
                'title': episode['title'],
                'url': episode['url'],
                'image_count': total_images,
                'downloaded_new': downloaded_count,
                'status': 'complete'
            }

        except Exception as e:
            print(f"  [ERROR] {e}", flush=True)
            return None


async def main():
    print("=" * 70, flush=True)
    print("Hand Jumper Smart Scraper", flush=True)
    print("Checks for missing images and downloads only what's needed", flush=True)
    print("=" * 70, flush=True)
    print(flush=True)

    # Scan existing data
    print("Scanning existing downloads...", flush=True)
    existing_data = get_existing_episodes()

    total_existing = sum(len(eps) for eps in existing_data.values())
    total_images = sum(
        ep_data['image_count']
        for season_eps in existing_data.values()
        for ep_data in season_eps.values()
    )

    print(f"Found {total_existing} existing episodes with {total_images} total images", flush=True)
    print(flush=True)

    # Fetch all episodes
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        all_episodes = await get_all_episodes(client)

        if not all_episodes:
            print("[ERROR] No episodes found!", flush=True)
            return

        print(f"\nProcessing {len(all_episodes)} episodes...", flush=True)
        print(flush=True)

        # Create semaphore for concurrent downloads
        semaphore = asyncio.Semaphore(CONCURRENT_EPISODES)

        # Download all episodes (with resume capability)
        tasks = []
        for episode in all_episodes:
            task = download_episode_images(client, episode, existing_data, semaphore)
            tasks.append(task)

        results = []
        for coro in asyncio.as_completed(tasks):
            result = await coro
            if result:
                results.append(result)

        # Save metadata
        metadata = {
            'total_episodes': len(results),
            'download_date': time.strftime('%Y-%m-%d %H:%M:%S'),
            'episodes': results,
            'config': {
                'concurrent_episodes': CONCURRENT_EPISODES,
                'delay_between_requests': DELAY_BETWEEN_REQUESTS,
                'max_retries': MAX_RETRIES
            }
        }

        METADATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(METADATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
        except OSError as e:
            print(f"[WARNING] Could not save metadata to {METADATA_FILE}: {e}", flush=True)

        # Summary
        new_downloads = sum(1 for r in results if r.get('status') != 'already_complete')
        already_complete = sum(1 for r in results if r.get('status') == 'already_complete')
        total_new_images = sum(r.get('downloaded_new', 0) for r in results)

        print(flush=True)
        print("=" * 70, flush=True)
        print("[OK] Scraping complete!", flush=True)
        print(f"[OK] Total episodes processed: {len(results)}", flush=True)
        print(f"[OK] Already complete: {already_complete}", flush=True)
        print(f"[OK] Downloaded/updated: {new_downloads}", flush=True)
        print(f"[OK] New images downloaded: {total_new_images}", flush=True)
        print(f"[OK] Metadata: {METADATA_FILE}", flush=True)
        print("=" * 70, flush=True)


if __name__ == "__main__":
    asyncio.run(main())
