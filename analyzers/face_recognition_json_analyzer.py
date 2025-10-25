"""
Face Recognition Analyzer Plugin (JSON-based)

Uses face_recognition library with JSON database (no pickle - more secure).
"""

from typing import List, Optional, Dict, Any, Tuple
import numpy as np
import json
from pathlib import Path
import cv2

from core.models import Character, BoundingBox
from core.analyzer_plugin import CharacterAnalyzerPlugin
from core.logger import get_logger

logger = get_logger(__name__)


class FaceRecognitionJSONAnalyzer(CharacterAnalyzerPlugin):
    """Character detection using face_recognition with JSON database."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.character_db: Dict[str, List[np.ndarray]] = {}
        self.tolerance = self.config.get('tolerance', 0.6)
        self.model = self.config.get('model', 'hog')  # hog or cnn
        self._load_character_database()

    @property
    def name(self) -> str:
        return "face_recognition_json_character_detector"

    @property
    def version(self) -> str:
        return "2.0.0"

    @property
    def dependencies(self) -> List[str]:
        return ['face_recognition']

    def _load_character_database(self) -> None:
        """Load character database from JSON file."""
        db_path = self.config.get('database_path', 'data/character_db.json')

        if not Path(db_path).exists():
            logger.warning(f"No character database found at {db_path}")
            logger.info("To create one, run: python scripts/build_character_database_json.py --mock")
            return

        try:
            with open(db_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Convert JSON encodings back to numpy arrays
            for char_name, char_data in data.get('characters', {}).items():
                encodings = []
                for enc_data in char_data.get('encodings', []):
                    # Convert list back to numpy array
                    encoding = np.array(enc_data['encoding'], dtype=np.float64)
                    encodings.append(encoding)

                if encodings:
                    self.character_db[char_name] = encodings

            logger.info(f"Loaded {len(self.character_db)} characters from JSON database")

            if data.get('mock'):
                logger.warning("Using MOCK character database - results are for testing only")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse character database (invalid JSON): {e}")
        except Exception as e:
            logger.error(f"Failed to load character database: {e}")

    def detect_characters(self, image: np.ndarray) -> List[Character]:
        """Detect and identify characters using face recognition."""
        if not self.check_dependencies():
            logger.warning("face_recognition not available, skipping")
            return []

        if not self.character_db:
            logger.warning("No character database loaded")
            return []

        import face_recognition

        # Convert BGR to RGB
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        # Detect faces
        face_locations = face_recognition.face_locations(image_rgb, model=self.model)

        if not face_locations:
            logger.debug("No faces detected")
            return []

        # Get face encodings
        face_encodings = face_recognition.face_encodings(image_rgb, face_locations)

        characters = []

        for (top, right, bottom, left), encoding in zip(face_locations, face_encodings):
            # Match against database
            match = self._match_character(encoding, face_recognition)

            if match:
                name, confidence = match
                characters.append(Character(
                    name=name,
                    confidence=confidence,
                    bbox=BoundingBox(left, top, right - left, bottom - top),
                    face_visible=True,
                    body_visible=False
                ))
                logger.debug(f"Detected character: {name} (confidence={confidence:.2f})")

        return characters

    def _match_character(self, encoding: np.ndarray, fr_module) -> Optional[Tuple[str, float]]:
        """Match face encoding against character database."""
        best_match = None
        best_distance = float('inf')

        for char_name, known_encodings in self.character_db.items():
            # Compare against all known encodings for this character
            distances = fr_module.face_distance(known_encodings, encoding)

            min_distance = float(np.min(distances))

            if min_distance < best_distance:
                best_distance = min_distance
                best_match = char_name

        # Convert distance to confidence (inverse relationship)
        if best_match and best_distance <= self.tolerance:
            confidence = 1.0 - (best_distance / self.tolerance)
            return (best_match, confidence)

        return None
