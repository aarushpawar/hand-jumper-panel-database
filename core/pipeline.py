"""
Pipeline Orchestration System

Manages the flow of panel processing through multiple analyzers.
Handles dependencies, parallel execution, and error recovery.
"""

from typing import List, Dict, Any, Optional, Callable
from pathlib import Path
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
from enum import Enum
import time
import cv2
import numpy as np

from .models import Panel, AnalysisResult, Tag, TagSource, TagCategory
from .analyzer_plugin import AnalyzerPlugin, PluginRegistry, get_registry
from .logger import get_logger

logger = get_logger(__name__)


class StageStatus(Enum):
    """Status of a pipeline stage."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StageResult:
    """Result of a pipeline stage execution."""
    stage_name: str
    status: StageStatus
    result: Optional[AnalysisResult] = None
    error: Optional[str] = None
    duration: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineContext:
    """Context passed through pipeline stages."""
    panel: Panel
    image: Optional[np.ndarray] = None
    intermediate_results: Dict[str, Any] = field(default_factory=dict)
    stage_results: List[StageResult] = field(default_factory=list)


class PipelineStage:
    """A single stage in the processing pipeline."""

    def __init__(
        self,
        name: str,
        analyzer: AnalyzerPlugin,
        dependencies: Optional[List[str]] = None
    ):
        self.name = name
        self.analyzer = analyzer
        self.dependencies = dependencies or []

    def can_execute(self, context: PipelineContext) -> bool:
        """Check if stage can execute (dependencies met)."""
        completed_stages = {
            sr.stage_name for sr in context.stage_results
            if sr.status == StageStatus.COMPLETED
        }
        return all(dep in completed_stages for dep in self.dependencies)

    def execute(self, context: PipelineContext) -> StageResult:
        """Execute the stage."""
        start_time = time.time()

        try:
            logger.info(f"Executing stage: {self.name}")

            # Run analyzer
            result = self.analyzer.analyze(context.image, Path(context.panel.path))

            # Store in context for dependent stages
            context.intermediate_results[self.name] = result

            duration = time.time() - start_time
            logger.info(f"Stage {self.name} completed in {duration:.2f}s")

            return StageResult(
                stage_name=self.name,
                status=StageStatus.COMPLETED,
                result=result,
                duration=duration
            )

        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Stage {self.name} failed: {e}", exc_info=True)

            return StageResult(
                stage_name=self.name,
                status=StageStatus.FAILED,
                error=str(e),
                duration=duration
            )


class Pipeline:
    """Main pipeline orchestrator."""

    def __init__(
        self,
        stages: Optional[List[PipelineStage]] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.stages = stages or []
        self.config = config or {}
        self.registry = get_registry()

        # Configuration
        self.continue_on_error = self.config.get('continue_on_error', True)
        self.max_workers = self.config.get('max_workers', 4)
        self.timeout = self.config.get('stage_timeout', 300)  # 5 min per stage

    def add_stage(
        self,
        name: str,
        analyzer: AnalyzerPlugin,
        dependencies: Optional[List[str]] = None
    ) -> None:
        """Add a stage to the pipeline."""
        stage = PipelineStage(name, analyzer, dependencies)
        self.stages.append(stage)
        logger.info(f"Added pipeline stage: {name}")

    def process_panel(self, panel: Panel) -> Panel:
        """
        Process a single panel through all stages.

        Args:
            panel: Panel to process

        Returns:
            Panel with analysis results
        """
        logger.info(f"Processing panel: {panel.id}")

        # Load image
        image = self._load_image(panel.path)
        if image is None:
            logger.error(f"Failed to load panel image: {panel.path}")
            return panel

        # Create context
        context = PipelineContext(panel=panel, image=image)

        # Execute stages in order
        for stage in self.stages:
            if not stage.can_execute(context):
                logger.warning(
                    f"Stage {stage.name} skipped (dependencies not met)"
                )
                context.stage_results.append(StageResult(
                    stage_name=stage.name,
                    status=StageStatus.SKIPPED
                ))
                continue

            result = stage.execute(context)
            context.stage_results.append(result)

            # Stop on error if configured
            if result.status == StageStatus.FAILED and not self.continue_on_error:
                logger.error(f"Pipeline stopped due to error in {stage.name}")
                break

        # Merge all results
        panel.ai_analysis = self._merge_results(context)

        return panel

    def process_panels(self, panels: List[Panel], parallel: bool = True) -> List[Panel]:
        """
        Process multiple panels.

        Args:
            panels: List of panels to process
            parallel: Whether to process in parallel

        Returns:
            List of processed panels
        """
        if parallel and self.max_workers > 1:
            return self._process_parallel(panels)
        else:
            return [self.process_panel(p) for p in panels]

    def _process_parallel(self, panels: List[Panel]) -> List[Panel]:
        """Process panels in parallel using thread pool."""
        results = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_panel = {
                executor.submit(self.process_panel, panel): panel
                for panel in panels
            }

            for future in as_completed(future_to_panel):
                try:
                    result = future.result(timeout=self.timeout)
                    results.append(result)
                except Exception as e:
                    panel = future_to_panel[future]
                    logger.error(f"Panel {panel.id} processing failed: {e}")
                    results.append(panel)  # Return unchanged panel

        return results

    def _load_image(self, path: str) -> Optional[np.ndarray]:
        """Load panel image."""
        try:
            img = cv2.imread(path)
            if img is None:
                # Try alternative path
                alt_path = self._find_alternative_path(path)
                if alt_path:
                    img = cv2.imread(alt_path)
            return img
        except Exception as e:
            logger.error(f"Failed to load image {path}: {e}")
            return None

    def _find_alternative_path(self, path: str) -> Optional[str]:
        """Try to find panel in alternative location."""
        # Extract filename and try in frontend/images
        path_obj = Path(path)
        filename = path_obj.name
        episode = path_obj.parent.name

        # Use relative path from project root
        project_root = Path(__file__).parent.parent
        alt_path = project_root / "frontend" / "images" / "s2" / episode / filename
        if alt_path.exists():
            return str(alt_path)

        return None

    def _merge_results(self, context: PipelineContext) -> AnalysisResult:
        """Merge results from all stages into single AnalysisResult."""
        merged = AnalysisResult()

        for stage_result in context.stage_results:
            if stage_result.status != StageStatus.COMPLETED:
                continue

            if stage_result.result:
                # Merge lists
                merged.characters.extend(stage_result.result.characters)
                merged.emotions.extend(stage_result.result.emotions)
                merged.dialogue.extend(stage_result.result.dialogue)
                merged.actions.extend(stage_result.result.actions)
                merged.tags.extend(stage_result.result.tags)

                # Use first non-None scene/visual
                if stage_result.result.scene and not merged.scene:
                    merged.scene = stage_result.result.scene
                if stage_result.result.visual and not merged.visual:
                    merged.visual = stage_result.result.visual

        # Calculate overall confidence
        confidences = [
            sr.result.overall_confidence
            for sr in context.stage_results
            if sr.status == StageStatus.COMPLETED and sr.result
        ]
        merged.overall_confidence = (
            sum(confidences) / len(confidences) if confidences else 0.0
        )

        # Generate combined tags
        merged.tags.extend(self._generate_summary_tags(merged))

        return merged

    def _generate_summary_tags(self, analysis: AnalysisResult) -> List[Tag]:
        """Generate summary tags from analysis."""
        tags = []

        # Character tags
        for char in analysis.characters:
            tags.append(Tag(
                category=TagCategory.CHARACTER,
                value=char.name,
                confidence=char.confidence,
                source=TagSource.AI
            ))

        # Emotion tags
        for emotion in analysis.emotions:
            tags.append(Tag(
                category=TagCategory.EMOTION,
                value=emotion.emotion,
                confidence=emotion.confidence,
                source=TagSource.AI,
                metadata={'character': emotion.character}
            ))

        # Action tags
        for action in analysis.actions:
            tags.append(Tag(
                category=TagCategory.ACTION,
                value=action.action,
                confidence=action.confidence,
                source=TagSource.AI
            ))

        # Scene tags
        if analysis.scene:
            if analysis.scene.setting:
                tags.append(Tag(
                    category=TagCategory.SCENE,
                    value=analysis.scene.setting,
                    confidence=analysis.scene.confidence,
                    source=TagSource.AI
                ))
            if analysis.scene.mood:
                tags.append(Tag(
                    category=TagCategory.SCENE,
                    value=analysis.scene.mood,
                    confidence=analysis.scene.confidence,
                    source=TagSource.AI
                ))

        return tags


class PipelineBuilder:
    """Builder for constructing pipelines."""

    def __init__(self):
        self.stages: List[tuple] = []
        self.config: Dict[str, Any] = {}

    def add_character_detection(self, analyzer: AnalyzerPlugin) -> 'PipelineBuilder':
        """Add character detection stage."""
        self.stages.append(('character_detection', analyzer, []))
        return self

    def add_emotion_detection(self, analyzer: AnalyzerPlugin) -> 'PipelineBuilder':
        """Add emotion detection stage (depends on character detection)."""
        self.stages.append(('emotion_detection', analyzer, ['character_detection']))
        return self

    def add_dialogue_detection(self, analyzer: AnalyzerPlugin) -> 'PipelineBuilder':
        """Add dialogue detection stage."""
        self.stages.append(('dialogue_detection', analyzer, []))
        return self

    def add_action_detection(self, analyzer: AnalyzerPlugin) -> 'PipelineBuilder':
        """Add action detection stage (depends on character detection)."""
        self.stages.append(('action_detection', analyzer, ['character_detection']))
        return self

    def add_scene_analysis(self, analyzer: AnalyzerPlugin) -> 'PipelineBuilder':
        """Add scene analysis stage."""
        self.stages.append(('scene_analysis', analyzer, []))
        return self

    def add_visual_analysis(self, analyzer: AnalyzerPlugin) -> 'PipelineBuilder':
        """Add visual analysis stage."""
        self.stages.append(('visual_analysis', analyzer, []))
        return self

    def configure(self, **kwargs) -> 'PipelineBuilder':
        """Set pipeline configuration."""
        self.config.update(kwargs)
        return self

    def build(self) -> Pipeline:
        """Build the pipeline."""
        pipeline = Pipeline(config=self.config)

        for name, analyzer, deps in self.stages:
            pipeline.add_stage(name, analyzer, deps)

        return pipeline
