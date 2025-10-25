"""
Image Optimization Script
Creates web-optimized versions of panels while preserving originals
Compresses to ~100-200KB per image for fast web loading
"""

from PIL import Image
from pathlib import Path
import json
from tqdm import tqdm
import os

# Use absolute paths relative to script location
SCRIPT_DIR = Path(__file__).parent.parent
INPUT_DIR = SCRIPT_DIR / "data" / "panels_original"
OUTPUT_DIR = SCRIPT_DIR / "data" / "panels_web"
METADATA_FILE = SCRIPT_DIR / "data" / "optimization_metadata.json"

# Optimization settings
MAX_WIDTH = 1200  # Max width for web version
MAX_HEIGHT = 2000  # Max height for web version
JPEG_QUALITY = 85  # Quality for JPEG compression (1-100)
TARGET_SIZE_KB = 200  # Target file size in KB


def get_file_size_kb(filepath):
    """Get file size in kilobytes"""
    return os.path.getsize(filepath) / 1024


def optimize_image(input_path, output_path, max_width=MAX_WIDTH, max_height=MAX_HEIGHT, quality=JPEG_QUALITY):
    """
    Optimize a single image for web use.

    Args:
        input_path: Path to original image
        output_path: Path for optimized image
        max_width: Maximum width in pixels
        max_height: Maximum height in pixels
        quality: JPEG quality (1-100)

    Returns:
        dict: Optimization results including success status, sizes, and dimensions
    """
    try:
        # Open image
        img = Image.open(input_path)

        # Convert RGBA to RGB if necessary
        if img.mode in ('RGBA', 'LA', 'P'):
            # Create white background
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
            img = background

        # Get original dimensions
        orig_width, orig_height = img.size
        orig_size_kb = get_file_size_kb(input_path)

        # Resize if too large
        needs_resize = orig_width > max_width or orig_height > max_height

        if needs_resize:
            # Calculate new dimensions maintaining aspect ratio
            ratio = min(max_width / orig_width, max_height / orig_height)
            new_width = int(orig_width * ratio)
            new_height = int(orig_height * ratio)

            # Use high-quality Lanczos resampling
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        else:
            new_width, new_height = orig_width, orig_height

        # Create output directory
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Save with optimization
        # Try progressive JPEG for better web loading
        img.save(
            output_path,
            'JPEG',
            quality=quality,
            optimize=True,
            progressive=True
        )

        # Check if we need to compress more
        current_size = get_file_size_kb(output_path)

        # If still too large, reduce quality iteratively
        current_quality = quality
        while current_size > TARGET_SIZE_KB and current_quality > 60:
            current_quality -= 5
            img.save(
                output_path,
                'JPEG',
                quality=current_quality,
                optimize=True,
                progressive=True
            )
            current_size = get_file_size_kb(output_path)

        final_size_kb = get_file_size_kb(output_path)

        return {
            'success': True,
            'original_size_kb': round(orig_size_kb, 2),
            'optimized_size_kb': round(final_size_kb, 2),
            'compression_ratio': round(orig_size_kb / final_size_kb, 2) if final_size_kb > 0 else 0,
            'original_dimensions': {'width': orig_width, 'height': orig_height},
            'optimized_dimensions': {'width': new_width, 'height': new_height},
            'final_quality': current_quality,
            'resized': needs_resize
        }

    except FileNotFoundError as e:
        return {
            'success': False,
            'error': f"File not found: {e}"
        }
    except OSError as e:
        return {
            'success': False,
            'error': f"OS error (disk space or permissions?): {e}"
        }
    except Exception as e:
        return {
            'success': False,
            'error': f"Unexpected error: {type(e).__name__}: {e}"
        }


def process_all_panels():
    """Process all extracted panels"""
    print("Image Optimization")
    print("=" * 50)
    print(f"Input: {INPUT_DIR}")
    print(f"Output: {OUTPUT_DIR}")
    print(f"Target size: ~{TARGET_SIZE_KB}KB per image")
    print(f"Max dimensions: {MAX_WIDTH}x{MAX_HEIGHT}")
    print()

    # Find all panel images
    all_images = list(INPUT_DIR.rglob('*.jpg')) + list(INPUT_DIR.rglob('*.png'))

    if not all_images:
        print("No images found to optimize!")
        return

    print(f"Found {len(all_images)} images to optimize")

    results = []
    total_original_size = 0
    total_optimized_size = 0

    # Process each image
    for img_path in tqdm(all_images, desc="Optimizing"):
        # Recreate directory structure in output
        relative_path = img_path.relative_to(INPUT_DIR)
        output_path = OUTPUT_DIR / relative_path.with_suffix('.jpg')

        # Optimize
        result = optimize_image(img_path, output_path)

        if result['success']:
            total_original_size += result['original_size_kb']
            total_optimized_size += result['optimized_size_kb']

            results.append({
                'input_file': str(img_path),
                'output_file': str(output_path),
                'relative_path': str(relative_path),
                **result
            })

    # Calculate statistics
    avg_compression = total_original_size / total_optimized_size if total_optimized_size > 0 else 0

    metadata = {
        'total_images': len(results),
        'successful': sum(1 for r in results if r['success']),
        'failed': sum(1 for r in results if not r['success']),
        'statistics': {
            'total_original_size_mb': round(total_original_size / 1024, 2),
            'total_optimized_size_mb': round(total_optimized_size / 1024, 2),
            'space_saved_mb': round((total_original_size - total_optimized_size) / 1024, 2),
            'average_compression_ratio': round(avg_compression, 2),
            'compression_percentage': round((1 - total_optimized_size/total_original_size) * 100, 1) if total_original_size > 0 else 0
        },
        'images': results
    }

    # Save metadata
    METADATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(METADATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    # Print summary
    print(f"\n✓ Optimization complete!")
    print(f"✓ Processed {metadata['successful']} images")
    print(f"✓ Original size: {metadata['statistics']['total_original_size_mb']} MB")
    print(f"✓ Optimized size: {metadata['statistics']['total_optimized_size_mb']} MB")
    print(f"✓ Space saved: {metadata['statistics']['space_saved_mb']} MB ({metadata['statistics']['compression_percentage']}% reduction)")
    print(f"✓ Average compression: {metadata['statistics']['average_compression_ratio']}x")
    print(f"✓ Metadata saved to {METADATA_FILE}")

    if metadata['failed'] > 0:
        print(f"\n⚠ Failed to optimize {metadata['failed']} images")


if __name__ == "__main__":
    process_all_panels()
