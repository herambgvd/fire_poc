"""
Stage 2 — YOLO11n object detector.
Activated only when Stage 1 escalates a flag.
Designed for high precision: confirm and localize fire/smoke with bounding boxes.
"""

import logging
import time

import cv2
import numpy as np
from ultralytics import YOLO

logger = logging.getLogger(__name__)


class Stage2Detector:
    """YOLO11n fire/smoke detector for confirmation + localization."""

    # Colors: fire → red, smoke → gray
    COLORS = {
        0: (0, 0, 255),      # Fire → red (BGR)
        1: (128, 128, 128),  # Smoke → gray
    }
    LABELS = {0: "Fire", 1: "Smoke"}

    def __init__(self, model_path: str):
        self.model = YOLO(model_path)
        # Force CPU
        self.model.to("cpu")
        # Pre-fuse the model so that predict() does not attempt to fuse
        # again from a background thread (which can crash with 'bn' errors).
        try:
            self.model.fuse()
        except Exception:
            pass  # already fused or not applicable
        logger.info(f"Stage 2 detector loaded from {model_path}")

    def predict(self, bgr_frame: np.ndarray, conf: float = 0.5,
                iou: float = 0.45) -> dict:
        """
        Run YOLO detection on a single BGR frame.

        Returns dict:
            confirmed   – bool  (fire or smoke found?)
            fire        – bool
            smoke       – bool
            boxes       – list[dict]  each: {xyxy, label, conf}
            annotated   – np.ndarray  frame with bounding box overlay
            time_ms     – float
        """
        t0 = time.perf_counter()
        results = self.model.predict(
            source=bgr_frame,
            conf=conf,
            iou=iou,
            verbose=False,
            device="cpu",
        )
        elapsed = (time.perf_counter() - t0) * 1000

        fire_found = False
        smoke_found = False
        boxes = []
        annotated = bgr_frame.copy()

        for r in results:
            for box, cls_id, confidence in zip(
                r.boxes.xyxy.cpu().numpy().astype(int),
                r.boxes.cls.cpu().numpy().astype(int),
                r.boxes.conf.cpu().numpy(),
            ):
                label = self.LABELS.get(cls_id, f"cls{cls_id}")
                color = self.COLORS.get(cls_id, (0, 255, 0))

                if cls_id == 0:
                    fire_found = True
                elif cls_id == 1:
                    smoke_found = True

                boxes.append({
                    "xyxy": box.tolist(),
                    "label": label,
                    "conf": float(confidence),
                })

                # Draw on annotated frame
                x1, y1, x2, y2 = box
                cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
                text = f"{label} {confidence:.2f}"
                cv2.putText(annotated, text, (x1, max(y1 - 8, 15)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        return {
            "confirmed": fire_found or smoke_found,
            "fire": fire_found,
            "smoke": smoke_found,
            "boxes": boxes,
            "annotated": annotated,
            "time_ms": elapsed,
        }
