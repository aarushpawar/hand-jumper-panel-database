"""
Unit tests for core data models.
"""

import pytest
from datetime import datetime
from core.models import (
    Panel, Episode, Database, Tag, TagCategory, TagSource,
    Character, Emotion, DialogueEntry, Action, SceneContext,
    VisualProperties, BoundingBox, AnalysisResult
)


class TestBoundingBox:
    """Test BoundingBox dataclass."""

    def test_creation(self):
        bbox = BoundingBox(x=10, y=20, width=100, height=50)
        assert bbox.x == 10
        assert bbox.y == 20
        assert bbox.width == 100
        assert bbox.height == 50

    def test_area(self):
        bbox = BoundingBox(x=0, y=0, width=100, height=50)
        assert bbox.area == 5000

    def test_intersects(self):
        bbox1 = BoundingBox(x=0, y=0, width=100, height=100)
        bbox2 = BoundingBox(x=50, y=50, width=100, height=100)
        bbox3 = BoundingBox(x=200, y=200, width=100, height=100)

        assert bbox1.intersects(bbox2)
        assert not bbox1.intersects(bbox3)

    def test_to_dict(self):
        bbox = BoundingBox(x=10, y=20, width=100, height=50)
        data = bbox.to_dict()
        assert data == {'x': 10, 'y': 20, 'width': 100, 'height': 50}


class TestTag:
    """Test Tag model."""

    def test_creation(self):
        tag = Tag(
            category=TagCategory.CHARACTER,
            value="Sayeon Lee",
            confidence=0.95,
            source=TagSource.AI
        )
        assert tag.category == TagCategory.CHARACTER
        assert tag.value == "Sayeon Lee"
        assert tag.confidence == 0.95
        assert tag.source == TagSource.AI

    def test_to_dict(self):
        tag = Tag(
            category=TagCategory.EMOTION,
            value="happy",
            confidence=0.85,
            source=TagSource.USER
        )
        data = tag.to_dict()
        assert data['category'] == 'emotion'
        assert data['value'] == 'happy'
        assert data['confidence'] == 0.85
        assert data['source'] == 'user'


class TestCharacter:
    """Test Character model."""

    def test_creation_minimal(self):
        char = Character(name="Sayeon Lee", confidence=0.9)
        assert char.name == "Sayeon Lee"
        assert char.confidence == 0.9
        assert char.bbox is None
        assert char.face_visible is True

    def test_creation_with_bbox(self):
        bbox = BoundingBox(x=10, y=20, width=100, height=150)
        char = Character(
            name="Jaehee",
            confidence=0.85,
            bbox=bbox,
            face_visible=True,
            body_visible=True
        )
        assert char.bbox.x == 10
        assert char.body_visible is True

    def test_to_dict(self):
        bbox = BoundingBox(x=10, y=20, width=100, height=150)
        char = Character(name="Test", confidence=0.9, bbox=bbox)
        data = char.to_dict()
        assert data['name'] == "Test"
        assert data['confidence'] == 0.9
        assert data['bbox']['x'] == 10


class TestPanel:
    """Test Panel model."""

    def test_creation(self):
        panel = Panel(
            id="ep001_p001",
            episode="ep001",
            panel_number=1,
            path="images/ep001/panel001.jpg",
            width=800,
            height=1200
        )
        assert panel.id == "ep001_p001"
        assert panel.episode == "ep001"
        assert panel.panel_number == 1
        assert panel.width == 800
        assert panel.height == 1200

    def test_get_characters_empty(self):
        panel = Panel(
            id="ep001_p001",
            episode="ep001",
            panel_number=1,
            path="test.jpg",
            width=800,
            height=1200
        )
        assert panel.get_characters() == []

    def test_get_characters_from_analysis(self):
        panel = Panel(
            id="ep001_p001",
            episode="ep001",
            panel_number=1,
            path="test.jpg",
            width=800,
            height=1200
        )
        char = Character(name="Sayeon", confidence=0.9)
        panel.ai_analysis = AnalysisResult(characters=[char])

        chars = panel.get_characters()
        assert "Sayeon" in chars

    def test_get_characters_from_user_tags(self):
        panel = Panel(
            id="ep001_p001",
            episode="ep001",
            panel_number=1,
            path="test.jpg",
            width=800,
            height=1200
        )
        tag = Tag(
            category=TagCategory.CHARACTER,
            value="Jaehee",
            confidence=1.0,
            source=TagSource.USER
        )
        panel.user_tags = [tag]

        chars = panel.get_characters()
        assert "Jaehee" in chars

    def test_get_tags_by_category(self):
        panel = Panel(
            id="ep001_p001",
            episode="ep001",
            panel_number=1,
            path="test.jpg",
            width=800,
            height=1200
        )
        tag1 = Tag(TagCategory.CHARACTER, "Sayeon", 0.9, TagSource.AI)
        tag2 = Tag(TagCategory.EMOTION, "happy", 0.8, TagSource.AI)
        panel.user_tags = [tag1, tag2]

        char_tags = panel.get_tags_by_category(TagCategory.CHARACTER)
        assert len(char_tags) == 1
        assert char_tags[0].value == "Sayeon"


class TestEpisode:
    """Test Episode model."""

    def test_creation(self):
        episode = Episode(id="ep001", number=1, title="First Day")
        assert episode.id == "ep001"
        assert episode.number == 1
        assert episode.title == "First Day"
        assert len(episode.panels) == 0

    def test_get_characters(self):
        panel1 = Panel("p1", "ep001", 1, "p1.jpg", 800, 1200)
        panel1.ai_analysis = AnalysisResult(
            characters=[Character("Sayeon", 0.9)]
        )

        panel2 = Panel("p2", "ep001", 2, "p2.jpg", 800, 1200)
        panel2.ai_analysis = AnalysisResult(
            characters=[Character("Jaehee", 0.85)]
        )

        episode = Episode(id="ep001", number=1, panels=[panel1, panel2])
        chars = episode.get_characters()

        assert "Sayeon" in chars
        assert "Jaehee" in chars
        assert len(chars) == 2

    def test_to_dict(self):
        episode = Episode(id="ep001", number=1, title="Test")
        data = episode.to_dict()
        assert data['id'] == "ep001"
        assert data['number'] == 1
        assert data['panel_count'] == 0


class TestDatabase:
    """Test Database model."""

    def test_creation(self):
        db = Database()
        assert db.version == "2.0"
        assert len(db.episodes) == 0

    def test_to_dict(self):
        ep = Episode(id="ep001", number=1)
        db = Database(episodes=[ep])
        data = db.to_dict()

        assert data['version'] == "2.0"
        assert data['total_episodes'] == 1
        assert data['total_panels'] == 0

    def test_panel_count(self):
        panel1 = Panel("p1", "ep001", 1, "p1.jpg", 800, 1200)
        panel2 = Panel("p2", "ep001", 2, "p2.jpg", 800, 1200)
        ep = Episode(id="ep001", number=1, panels=[panel1, panel2])
        db = Database(episodes=[ep])

        data = db.to_dict()
        assert data['total_panels'] == 2


class TestAnalysisResult:
    """Test AnalysisResult model."""

    def test_creation_empty(self):
        result = AnalysisResult()
        assert len(result.characters) == 0
        assert len(result.emotions) == 0
        assert len(result.dialogue) == 0
        assert len(result.actions) == 0
        assert result.scene is None
        assert result.visual is None

    def test_to_dict(self):
        char = Character("Sayeon", 0.9)
        emotion = Emotion("Sayeon", "determined", 0.85)
        result = AnalysisResult(
            characters=[char],
            emotions=[emotion],
            overall_confidence=0.87
        )

        data = result.to_dict()
        assert len(data['characters']) == 1
        assert len(data['emotions']) == 1
        assert data['overall_confidence'] == 0.87


class TestEnums:
    """Test enum values."""

    def test_tag_category_values(self):
        assert TagCategory.CHARACTER.value == "character"
        assert TagCategory.EMOTION.value == "emotion"
        assert TagCategory.ACTION.value == "action"
        assert TagCategory.DIALOGUE.value == "dialogue"
        assert TagCategory.SCENE.value == "scene"
        assert TagCategory.VISUAL.value == "visual"
        assert TagCategory.CUSTOM.value == "custom"
        assert TagCategory.OTHER.value == "other"

    def test_tag_source_values(self):
        assert TagSource.AI.value == "ai"
        assert TagSource.USER.value == "user"
        assert TagSource.HYBRID.value == "hybrid"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
