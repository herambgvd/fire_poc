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


def _overlap_frac(box, persons) -> float:
    """Fraction of ``box``'s area that falls inside any person box (0-1)."""
    x1, y1, x2, y2 = box
    area = max(1, (x2 - x1)) * max(1, (y2 - y1))
    best = 0.0
    for p in persons:
        px1, py1, px2, py2 = p
        iw = max(0, min(x2, px2) - max(x1, px1))
        ih = max(0, min(y2, py2) - max(y1, py1))
        best = max(best, (iw * ih) / area)
    return best


class Stage2Detector:
    """YOLO11n fire/smoke detector for confirmation + localization."""

    # Colors: fire → red, smoke → gray
    COLORS = {
        0: (0, 0, 255),      # Fire → red (BGR)
        1: (128, 128, 128),  # Smoke → gray
    }
    LABELS = {0: "Fire", 1: "Smoke"}

    def __init__(self, model_path: str, device: str | None = None,
                 person_detector=None):
        self.model = YOLO(model_path)
        self.person_detector = person_detector   # optional PersonGuard
        # Use CUDA when available (GPU box), else CPU. Explicit device overrides.
        if device is None:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = device
        self.model.to(device)
        # Pre-fuse the model so that predict() does not attempt to fuse
        # again from a background thread (which can crash with 'bn' errors).
        try:
            self.model.fuse()
        except Exception:
            pass  # already fused or not applicable
        logger.info(f"Stage 2 detector loaded from {model_path} (device={device})")

    def predict(self, bgr_frame: np.ndarray, conf: float = 0.5,
                iou: float = 0.45, roi=None,
                suppress_person: bool = False, person_overlap: float = 0.35) -> dict:
        """
        Run YOLO detection on a single BGR frame.

        ``roi`` (optional): [x1, y1, x2, y2] normalized 0-1. Detections whose box
        centre falls outside the ROI are ignored (not counted, not drawn); the ROI
        outline is drawn on the annotated frame so the monitored zone is visible.

        Returns dict:
            confirmed   – bool  (fire or smoke found INSIDE the ROI?)
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
            device=self.device,
        )
        elapsed = (time.perf_counter() - t0) * 1000

        h, w = bgr_frame.shape[:2]
        rx1 = ry1 = 0
        rx2, ry2 = w, h
        if roi and len(roi) == 4:
            rx1, ry1, rx2, ry2 = (int(roi[0] * w), int(roi[1] * h),
                                  int(roi[2] * w), int(roi[3] * h))

        fire_found = False
        smoke_found = False
        boxes = []
        annotated = bgr_frame.copy()

        # Draw the ROI zone first (so boxes render on top).
        if roi and len(roi) == 4:
            cv2.rectangle(annotated, (rx1, ry1), (rx2, ry2), (80, 220, 80), 2)
            cv2.putText(annotated, "ROI", (rx1 + 5, max(ry1 + 18, 18)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (80, 220, 80), 1)

        # Pass 1 — collect candidate detections, gated by the ROI.
        cand = []
        for r in results:
            for box, cls_id, confidence in zip(
                r.boxes.xyxy.cpu().numpy().astype(int),
                r.boxes.cls.cpu().numpy().astype(int),
                r.boxes.conf.cpu().numpy(),
            ):
                x1, y1, x2, y2 = box
                if roi and len(roi) == 4:
                    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
                    if not (rx1 <= cx <= rx2 and ry1 <= cy <= ry2):
                        continue
                cand.append((box, int(cls_id), float(confidence)))

        # Person suppression — drop fire/smoke boxes that mostly overlap a person
        # (e.g. a yellow shirt misread as fire). Only runs when there is a
        # candidate, so the extra model is skipped on empty frames.
        if suppress_person and self.person_detector is not None and cand:
            persons = self.person_detector.persons(bgr_frame)
            if persons:
                cand = [c for c in cand if _overlap_frac(c[0], persons) <= person_overlap]

        # Pass 2 — count + draw the survivors.
        for box, cls_id, confidence in cand:
            x1, y1, x2, y2 = box
            label = self.LABELS.get(cls_id, f"cls{cls_id}")
            color = self.COLORS.get(cls_id, (0, 255, 0))
            if cls_id == 0:
                fire_found = True
            elif cls_id == 1:
                smoke_found = True
            boxes.append({"xyxy": box.tolist(), "label": label, "conf": float(confidence)})
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
            cv2.putText(annotated, f"{label} {confidence:.2f}", (x1, max(y1 - 8, 15)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        return {
            "confirmed": fire_found or smoke_found,
            "fire": fire_found,
            "smoke": smoke_found,
            "boxes": boxes,
            "annotated": annotated,
            "time_ms": elapsed,
        }
