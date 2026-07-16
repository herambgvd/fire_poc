"""Person guard — a general COCO YOLO used only to veto false fire/smoke boxes.

The fire/smoke model sometimes reads warm-coloured clothing (a yellow/orange
shirt) as fire. This detects people (COCO class 0) so the pipeline can drop any
fire/smoke box that mostly overlaps a person. Kept separate from the fire model
so it stays optional and easy to disable.
"""

from __future__ import annotations

import logging

import numpy as np
from ultralytics import YOLO

logger = logging.getLogger(__name__)


class PersonGuard:
    """Detects people (COCO class 0) for false-positive suppression."""

    def __init__(self, model_path: str = "yolo11n.pt", device: str | None = None,
                 conf: float = 0.35):
        self.model = YOLO(model_path)
        if device is None:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = device
        self.conf = conf
        self.model.to(device)
        try:
            self.model.fuse()
        except Exception:
            pass
        logger.info("Person guard loaded (%s, device=%s)", model_path, device)

    def persons(self, bgr_frame: np.ndarray) -> list[list[int]]:
        """Return person boxes [[x1,y1,x2,y2], ...] in the frame."""
        res = self.model.predict(
            source=bgr_frame, conf=self.conf, classes=[0],
            verbose=False, device=self.device,
        )
        out: list[list[int]] = []
        for r in res:
            for box in r.boxes.xyxy.cpu().numpy().astype(int):
                out.append(box.tolist())
        return out
