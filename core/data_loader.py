"""
Data Loader - Bridge between existing database and new architecture

Handles loading existing panel data and saving results back.
"""

import json
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime

from .models import (
    Database, Episode, Panel, AnalysisResult, Tag, TagSource, TagCategory,
    Character, Emotion, DialogueEntry, Action, SceneContext, VisualProperties,
    BoundingBox
)


def load_existing_database(path: str) -> Database:
    """Load existing panel database and convert to new format."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in database file {path}: {e}")
    except FileNotFoundError:
        raise FileNotFoundError(f"Database file not found: {path}")

    # Group panels by episode
    panels_by_episode: Dict[int, List[Dict]] = {}
    for panel_data in data.get('panels', []):
        ep_num = panel_data['episode']
        if ep_num not in panels_by_episode:
            panels_by_episode[ep_num] = []
        panels_by_episode[ep_num].append(panel_data)

    # Create episodes
    episodes = []
    for ep_num in sorted(panels_by_episode.keys()):
        panels = []
        ep_panels_data = panels_by_episode[ep_num]
        for panel_data in ep_panels_data:
            panel = _convert_panel(panel_data)
            panels.append(panel)

        # Get season from first panel in episode
        season = ep_panels_data[0].get('season', 2) if ep_panels_data else 2
        episode = Episode(
            id=f"s{season}_ep{ep_num:03d}",
            number=ep_num,
            title=f"Season {season}, Episode {ep_num}",
            panels=panels,
            metadata={'season': season}
        )
        episodes.append(episode)

    db = Database(
        episodes=episodes,
        version=data.get('version', '2.0'),
        created_at=data.get('created', datetime.now().isoformat()),
        updated_at=datetime.now().isoformat()
    )

    return db


def _convert_panel(data: Dict[str, Any]) -> Panel:
    """Convert old panel format to new Panel model."""
    panel_id = data['id']

    # Load existing AI analysis if present
    ai_analysis = None
    automated = data.get('automated', {})
    if automated.get('detected'):
        ai_analysis = _convert_automated_tags(automated)

    # Load user tags if present
    user_tags = []
    manual = data.get('manual', {})
    if manual.get('tags'):
        user_tags = _convert_manual_tags(manual)

    # Create panel
    panel = Panel(
        id=panel_id,
        episode=f"ep{data['episode']:03d}",
        panel_number=data['panelNumber'],
        path=data['imagePath'],
        width=data['dimensions']['width'],
        height=data['dimensions']['height'],
        ai_analysis=ai_analysis,
        user_tags=user_tags
    )

    return panel


def _convert_automated_tags(automated: Dict[str, Any]) -> AnalysisResult:
    """Convert old automated tags to AnalysisResult."""
    # For now, create a simple conversion
    # The old format has detected: [] and confidence: {}
    # We'll map this to our new structure
    tags = []
    for tag in automated.get('detected', []):
        # Try to guess category from tag content
        category = TagCategory.OTHER
        if any(emotion in tag.lower() for emotion in ['happy', 'sad', 'angry', 'surprised']):
            category = TagCategory.EMOTION

        tags.append(Tag(
            category=category,
            value=tag,
            confidence=automated.get('confidence', {}).get(tag, 0.0),
            source=TagSource.AI
        ))

    return AnalysisResult(tags=tags)


def _convert_manual_tags(manual: Dict[str, Any]) -> List[Tag]:
    """Convert old manual tags to new Tag format."""
    tags = []

    # Characters
    for char in manual.get('characters', []):
        tags.append(Tag(
            category=TagCategory.CHARACTER,
            value=char,
            confidence=1.0,
            source=TagSource.USER
        ))

    # Emotions
    for emotion in manual.get('emotions', []):
        tags.append(Tag(
            category=TagCategory.EMOTION,
            value=emotion,
            confidence=1.0,
            source=TagSource.USER
        ))

    # Locations (map to scene)
    for location in manual.get('locations', []):
        tags.append(Tag(
            category=TagCategory.SCENE,
            value=location,
            confidence=1.0,
            source=TagSource.USER
        ))

    # Generic tags
    for tag in manual.get('tags', []):
        tags.append(Tag(
            category=TagCategory.OTHER,
            value=tag,
            confidence=1.0,
            source=TagSource.USER
        ))

    return tags


def save_to_frontend_format(db: Database, path: str) -> None:
    """Save database back to frontend-compatible format."""
    # Flatten all panels from all episodes
    panels = []
    for episode in db.episodes:
        for panel in episode.panels:
            panel_data = _convert_panel_to_old_format(panel, episode)
            panels.append(panel_data)

    # Create output structure
    output = {
        'version': db.version,
        'created': db.created_at,
        'updated': db.updated_at,
        'description': 'Panel database with ML analysis',
        'schema': '2.0',
        'panels': panels
    }

    with open(path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)


def _convert_panel_to_old_format(panel: Panel, episode: Episode) -> Dict[str, Any]:
    """Convert new Panel model back to old format."""
    # Extract automated tags
    automated = {'detected': [], 'confidence': {}}
    if panel.ai_analysis:
        for tag in panel.ai_analysis.tags:
            tag_str = f"{tag.category.value}:{tag.value}"
            automated['detected'].append(tag_str)
            automated['confidence'][tag_str] = tag.confidence

        # Also add detailed analysis
        for char in panel.ai_analysis.characters:
            char_tag = f"character:{char.name}"
            if char_tag not in automated['detected']:
                automated['detected'].append(char_tag)
                automated['confidence'][char_tag] = char.confidence

        for emotion in panel.ai_analysis.emotions:
            emotion_tag = f"emotion:{emotion.emotion}"
            if emotion_tag not in automated['detected']:
                automated['detected'].append(emotion_tag)
                automated['confidence'][emotion_tag] = emotion.confidence

    # Extract manual tags
    manual = {
        'characters': [],
        'emotions': [],
        'locations': [],
        'tags': [],
        'action': False,
        'dialogue': False,
        'items': [],
        'organizations': [],
        'plotPoints': [],
        'notes': ''
    }

    for tag in panel.user_tags:
        if tag.category == TagCategory.CHARACTER:
            manual['characters'].append(tag.value)
        elif tag.category == TagCategory.EMOTION:
            manual['emotions'].append(tag.value)
        elif tag.category == TagCategory.SCENE:
            manual['locations'].append(tag.value)
        else:
            manual['tags'].append(tag.value)

    # Build panel data
    return {
        'id': panel.id,
        'season': episode.metadata.get('season', 2),
        'episode': episode.number,
        'panelNumber': panel.panel_number,
        'imagePath': panel.path,
        'originalPath': panel.path,  # May need adjustment
        'dimensions': {
            'width': panel.width,
            'height': panel.height
        },
        'automated': automated,
        'manual': manual,
        'metadata': {
            'tagged': len(automated['detected']) > 0,
            'verified': False,
            'lastModified': datetime.now().isoformat(),
            'filesize': 0
        }
    }
