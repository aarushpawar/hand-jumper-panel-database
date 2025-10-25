"""
Core Domain Models

Defines the fundamental data structures for the panel database system.
All models use dataclasses with JSON serialization support.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any
from datetime import datetime
from enum import Enum
import json


class TagSource(Enum):
    """Source of a tag."""
    AI = "ai"
    USER = "user"
    HYBRID = "hybrid"  # AI + user verified


class TagCategory(Enum):
    """Category of tag."""
    CHARACTER = "character"
    EMOTION = "emotion"
    ACTION = "action"
    DIALOGUE = "dialogue"
    SCENE = "scene"
    VISUAL = "visual"
    CUSTOM = "custom"
    OTHER = "other"  # Generic/uncategorized tags


@dataclass
class BoundingBox:
    """Bounding box coordinates."""
    x: int
    y: int
    width: int
    height: int

    def to_dict(self) -> Dict[str, int]:
        return asdict(self)

    @property
    def area(self) -> int:
        return self.width * self.height

    def intersects(self, other: 'BoundingBox') -> bool:
        """Check if this bbox intersects with another."""
        return not (
            self.x + self.width < other.x or
            other.x + other.width < self.x or
            self.y + self.height < other.y or
            other.y + other.height < self.y
        )


@dataclass
class Tag:
    """A single tag with metadata."""
    category: TagCategory
    value: str
    confidence: float
    source: TagSource
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            'category': self.category.value,
            'value': self.value,
            'confidence': self.confidence,
            'source': self.source.value,
            'metadata': self.metadata,
            'created_at': self.created_at
        }


@dataclass
class Character:
    """Detected character in a panel."""
    name: str
    confidence: float
    bbox: Optional[BoundingBox] = None
    face_visible: bool = True
    body_visible: bool = False
    attributes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'confidence': self.confidence,
            'bbox': self.bbox.to_dict() if self.bbox else None,
            'face_visible': self.face_visible,
            'body_visible': self.body_visible,
            'attributes': self.attributes
        }


@dataclass
class Emotion:
    """Detected emotion."""
    character: str
    emotion: str
    confidence: float
    intensity: float = 0.5
    distribution: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'character': self.character,
            'emotion': self.emotion,
            'confidence': self.confidence,
            'intensity': self.intensity,
            'distribution': self.distribution
        }


@dataclass
class DialogueEntry:
    """Text/dialogue in a panel."""
    text: str
    confidence: float
    bbox: Optional[BoundingBox] = None
    language: str = "en"
    speaker: Optional[str] = None
    text_type: str = "dialogue"  # dialogue, narration, sound_effect

    def to_dict(self) -> Dict[str, Any]:
        return {
            'text': self.text,
            'confidence': self.confidence,
            'bbox': self.bbox.to_dict() if self.bbox else None,
            'language': self.language,
            'speaker': self.speaker,
            'type': self.text_type
        }


@dataclass
class Action:
    """Detected action in panel."""
    action: str
    characters: List[str]
    confidence: float
    intensity: float = 0.5
    attributes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'action': self.action,
            'characters': self.characters,
            'confidence': self.confidence,
            'intensity': self.intensity,
            'attributes': self.attributes
        }


@dataclass
class SceneContext:
    """Scene/environment context."""
    setting: str
    confidence: float
    location: Optional[str] = None
    time_of_day: Optional[str] = None
    weather: Optional[str] = None
    mood: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class VisualProperties:
    """Visual characteristics of panel."""
    dominant_colors: List[List[int]]
    brightness: float
    contrast: float
    color_palette: str = "balanced"
    attributes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AnalysisResult:
    """Complete analysis result for a panel."""
    characters: List[Character] = field(default_factory=list)
    emotions: List[Emotion] = field(default_factory=list)
    dialogue: List[DialogueEntry] = field(default_factory=list)
    actions: List[Action] = field(default_factory=list)
    scene: Optional[SceneContext] = None
    visual: Optional[VisualProperties] = None
    tags: List[Tag] = field(default_factory=list)
    overall_confidence: float = 0.0
    analyzer_version: str = "1.0"
    analyzed_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            'characters': [c.to_dict() for c in self.characters],
            'emotions': [e.to_dict() for e in self.emotions],
            'dialogue': [d.to_dict() for d in self.dialogue],
            'actions': [a.to_dict() for a in self.actions],
            'scene': self.scene.to_dict() if self.scene else None,
            'visual': self.visual.to_dict() if self.visual else None,
            'tags': [t.to_dict() for t in self.tags],
            'overall_confidence': self.overall_confidence,
            'analyzer_version': self.analyzer_version,
            'analyzed_at': self.analyzed_at
        }


@dataclass
class Panel:
    """A single panel with all metadata."""
    id: str
    episode: str
    panel_number: int
    path: str
    width: int
    height: int

    # Analysis results
    ai_analysis: Optional[AnalysisResult] = None
    user_tags: List[Tag] = field(default_factory=list)

    # Metadata
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    version: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'episode': self.episode,
            'panel_number': self.panel_number,
            'path': self.path,
            'dimensions': {'width': self.width, 'height': self.height},
            'ai_analysis': self.ai_analysis.to_dict() if self.ai_analysis else None,
            'user_tags': [t.to_dict() for t in self.user_tags],
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'version': self.version
        }

    def get_all_tags(self) -> List[Tag]:
        """Get all tags (AI + user)."""
        tags = list(self.user_tags)
        if self.ai_analysis:
            tags.extend(self.ai_analysis.tags)
        return tags

    def get_tags_by_category(self, category: TagCategory) -> List[Tag]:
        """Get tags filtered by category."""
        return [t for t in self.get_all_tags() if t.category == category]

    def get_characters(self) -> List[str]:
        """Get all character names."""
        chars = []
        if self.ai_analysis:
            chars.extend([c.name for c in self.ai_analysis.characters])
        chars.extend([
            t.value for t in self.user_tags
            if t.category == TagCategory.CHARACTER
        ])
        return list(set(chars))


@dataclass
class Episode:
    """An episode with its panels."""
    id: str
    number: int
    title: Optional[str] = None
    panels: List[Panel] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'number': self.number,
            'title': self.title,
            'panel_count': len(self.panels),
            'panels': [p.to_dict() for p in self.panels],
            'metadata': self.metadata
        }

    def get_characters(self) -> List[str]:
        """Get all unique characters in episode."""
        chars = set()
        for panel in self.panels:
            chars.update(panel.get_characters())
        return sorted(list(chars))


@dataclass
class Database:
    """Complete panel database."""
    episodes: List[Episode] = field(default_factory=list)
    version: str = "2.0"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'version': self.version,
            'total_episodes': len(self.episodes),
            'total_panels': sum(len(ep.panels) for ep in self.episodes),
            'episodes': [ep.to_dict() for ep in self.episodes],
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'metadata': self.metadata
        }

    def save(self, path: str) -> None:
        """Save database to JSON file."""
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, path: str) -> 'Database':
        """Load database from JSON file."""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in file {path}: {e}")
        except FileNotFoundError:
            raise FileNotFoundError(f"Database file not found: {path}")

        # Reconstruct database (simplified - in production, use proper deserialization)
        db = cls(
            version=data.get('version', '2.0'),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at'),
            metadata=data.get('metadata', {})
        )
        return db
