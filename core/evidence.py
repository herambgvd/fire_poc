"""
Evidence clip assembly.

Stitches all frames into a single MP4 evidence file.
Both pre-detection (buffer) and post-detection frames are expected to
already have Stage 2 bounding box annotations where applicable.
"""

import logging
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from config import EVIDENCE_DIR

logger = logging.getLogger(__name__)


def assemble_evidence(pre_frames: list, post_frames: list,
                      camera_name: str, detection_type: str,
                      output_size: tuple = (640, 480),
                      fps: float = 15.0) -> str | None:
    """
    Build an evidence MP4 clip from annotated frame data.

    Args:
        pre_frames:  list of (timestamp, bgr_ndarray) — annotated buffer frames
        post_frames: list of (timestamp, bgr_ndarray) — annotated recording frames
        camera_name: camera identifier for filename
        detection_type: "Fire" or "Smoke"
        output_size: (width, height) of the output video
        fps: frame rate for the output video

    Returns:
        Path to the saved evidence file, or None on failure.
    """
    if not pre_frames and not post_frames:
        logger.warning("No frames for evidence assembly")
        return None

    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_cam = camera_name.replace(" ", "_").replace("/", "_")
    filename = f"{timestamp}_{safe_cam}_{detection_type}.mp4"
    filepath = EVIDENCE_DIR / filename

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(filepath), fourcc, fps,
                             output_size)

    if not writer.isOpened():
        logger.error(f"Failed to create video writer: {filepath}")
        return None

    frame_count = 0

    # ── Write pre-detection frames (buffer, annotated by Stage 2) ──
    for ts, frame in pre_frames:
        if frame is not None:
            resized = cv2.resize(frame, output_size)
            # Add "PRE-DETECTION" watermark
            cv2.putText(resized, "PRE-DETECTION", (10, 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
            writer.write(resized)
            frame_count += 1

    # ── Write post-detection frames (recorded after escalation) ──
    for ts, frame in post_frames:
        if frame is not None:
            resized = cv2.resize(frame, output_size)
            cv2.putText(resized, f"DETECTION: {detection_type.upper()}", (10, 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            writer.write(resized)
            frame_count += 1

    writer.release()
    logger.info(f"Evidence saved: {filepath} ({frame_count} frames, "
                f"{frame_count / fps:.1f}s)")
    return str(filepath)
