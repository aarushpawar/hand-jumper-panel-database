#!/usr/bin/env python3
"""
Build Character Database (JSON Format)

Creates a JSON-based character database instead of pickle for better security.
Uses face_recognition to create encodings from character images.

Usage:
    python build_character_database_json.py --input data/character_images --output data/character_db.json
"""

import argparse
import json
from pathlib import Path
from typing import Dict, List
import sys

import numpy as np

try:
    import face_recognition
    import cv2
    HAS_FACE_RECOGNITION = True
except ImportError:
    HAS_FACE_RECOGNITION = False
    print("Warning: face_recognition not available. Will create mock database.")


def build_character_database(input_dir: Path, output_path: Path, model: str = "hog") -> None:
    """
    Build character database from images.

    Args:
        input_dir: Directory containing character subdirectories with images
        output_path: Path to save JSON database
        model: Face detection model ('hog' or 'cnn')
    """
    if not HAS_FACE_RECOGNITION:
        create_mock_database(output_path)
        return

    print(f"Building character database from {input_dir}")
    print(f"Using {model} model for face detection")

    database = {
        "version": "2.0",
        "model": model,
        "characters": {}
    }

    character_dirs = [d for d in input_dir.iterdir() if d.is_dir()]

    for char_dir in sorted(character_dirs):
        char_name = char_dir.name
        print(f"\nProcessing character: {char_name}")

        encodings_list = []
        image_files = list(char_dir.glob("*.jpg")) + list(char_dir.glob("*.png"))

        if not image_files:
            print(f"  Warning: No images found for {char_name}")
            continue

        for img_path in image_files:
            try:
                # Load image
                image = face_recognition.load_image_file(str(img_path))

                # Detect faces
                face_locations = face_recognition.face_locations(image, model=model)

                if not face_locations:
                    print(f"  No face detected in {img_path.name}")
                    continue

                # Get encoding (use first face)
                encodings = face_recognition.face_encodings(image, face_locations)
                if encodings:
                    # Convert numpy array to list for JSON serialization
                    encoding_list = encodings[0].tolist()
                    encodings_list.append({
                        "encoding": encoding_list,
                        "source_image": img_path.name,
                        "face_location": face_locations[0]
                    })
                    print(f"  ✓ Encoded {img_path.name}")

            except Exception as e:
                print(f"  Error processing {img_path.name}: {e}")

        if encodings_list:
            database["characters"][char_name] = {
                "name": char_name,
                "num_encodings": len(encodings_list),
                "encodings": encodings_list
            }
            print(f"  Total: {len(encodings_list)} encodings for {char_name}")
        else:
            print(f"  Warning: No valid encodings for {char_name}")

    # Save database
    print(f"\nSaving database to {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(database, f, indent=2)

    # Print summary
    total_encodings = sum(
        char["num_encodings"]
        for char in database["characters"].values()
    )
    print(f"\nDatabase created successfully!")
    print(f"  Characters: {len(database['characters'])}")
    print(f"  Total encodings: {total_encodings}")
    print(f"  Size: {output_path.stat().st_size / 1024:.1f} KB")


def create_mock_database(output_path: Path) -> None:
    """
    Create a mock database for testing when face_recognition is not available.
    """
    print("Creating mock character database...")

    # Mock characters from Hand Jumper
    characters = [
        "Sayeon Lee",
        "Jaehee Han",
        "Ryujin Kang",
        "Min",
        "Samin Lee",
        "Iseul Kim",
        "Juni Chang"
    ]

    database = {
        "version": "2.0",
        "model": "mock",
        "mock": True,
        "characters": {}
    }

    # Create mock encodings (128-dimensional vectors)
    for i, char_name in enumerate(characters):
        # Generate deterministic "encoding" for consistency
        np.random.seed(i)
        mock_encoding = np.random.randn(128).tolist()

        database["characters"][char_name] = {
            "name": char_name,
            "num_encodings": 1,
            "encodings": [{
                "encoding": mock_encoding,
                "source_image": "mock.jpg",
                "face_location": [0, 100, 100, 0]
            }]
        }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(database, f, indent=2)

    print(f"Mock database created at {output_path}")
    print(f"  Characters: {len(characters)}")


def load_character_database(db_path: Path) -> Dict:
    """
    Load character database from JSON.

    Args:
        db_path: Path to JSON database

    Returns:
        Dict with character data
    """
    with open(db_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(
        description="Build character database from images (JSON format)"
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/character_images"),
        help="Directory containing character subdirectories"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/character_db.json"),
        help="Output JSON database path"
    )
    parser.add_argument(
        "--model",
        choices=["hog", "cnn"],
        default="hog",
        help="Face detection model (hog=faster, cnn=more accurate)"
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Create mock database for testing"
    )

    args = parser.parse_args()

    if args.mock or not HAS_FACE_RECOGNITION:
        create_mock_database(args.output)
    elif not args.input.exists():
        print(f"Error: Input directory not found: {args.input}")
        print("\nTo use this script:")
        print("1. Create data/character_images directory")
        print("2. Add subdirectories for each character")
        print("3. Add character face images to each subdirectory")
        print("\nExample structure:")
        print("  data/character_images/")
        print("    Sayeon Lee/")
        print("      sayeon_01.jpg")
        print("      sayeon_02.jpg")
        print("    Jaehee Han/")
        print("      jaehee_01.jpg")
        print("\nOr use --mock to create a mock database for testing")
        sys.exit(1)
    else:
        build_character_database(args.input, args.output, args.model)


if __name__ == "__main__":
    main()
