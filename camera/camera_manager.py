"""
Multi-camera manager.
Creates and manages CameraSource + CameraPipeline pairs.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from camera.camera_source import CameraSource

if TYPE_CHECKING:
    from core.stage1_classifier import Stage1Classifier
    from core.stage2_detector import Stage2Detector

logger = logging.getLogger(__name__)


class CameraManager:
    """Manages multiple camera feeds and their detection pipelines."""

    def __init__(self, classifier: Stage1Classifier,
                 detector: Stage2Detector,
                 alert_callback=None):
        self.classifier = classifier
        self.detector = detector
        self.alert_callback = alert_callback

        self.sources: dict[str, CameraSource] = {}
        self.pipelines: dict = {}  # str → CameraPipeline (lazy-imported)

    def add_camera(self, name: str, source, loop: bool = False) -> bool:
        """
        Add a camera and create its pipeline.

        Args:
            name: Unique camera name
            source: URL string, device index, or file path
            loop: Loop video (for test mode)
        """
        cam = CameraSource(source=source, name=name, loop=loop)
        if not cam.open():
            return False

        from core.pipeline import CameraPipeline  # lazy import
        pipe = CameraPipeline(
            camera_name=name,
            classifier=self.classifier,
            detector=self.detector,
            alert_callback=self.alert_callback,
        )
        pipe.set_source(cam)

        self.sources[name] = cam
        self.pipelines[name] = pipe
        logger.info(f"Camera added: {name} → {source}")
        return True

    def start_all(self):
        for name, pipe in self.pipelines.items():
            pipe.start()

    def stop_all(self):
        for name, pipe in self.pipelines.items():
            pipe.stop()
        for name, cam in self.sources.items():
            cam.release()
        logger.info("All cameras stopped and released")

    def remove_camera(self, name: str):
        if name in self.pipelines:
            self.pipelines[name].stop()
            del self.pipelines[name]
        if name in self.sources:
            self.sources[name].release()
            del self.sources[name]

    @property
    def camera_names(self):
        return list(self.sources.keys())
