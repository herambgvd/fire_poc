"""
Evidence clip assembly.

Stitches all frames into a single MP4 evidence file.
Both pre-detection (buffer) and post-detection frames are expected to
already have Stage 2 bounding box annotations where applicable.
"""

import logging
import os
import subprocess
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from config import EVIDENCE_DIR

logger = logging.getLogger(__name__)


def _transcode_h264(src: str, dst: str) -> bool:
    """Re-encode ``src`` to browser-playable H.264 MP4 (faststart) at ``dst``.

    OpenCV's VideoWriter emits MPEG-4 Part 2 (mp4v/mpeg4), which browsers can't
    play. ffmpeg (bundled in the image) converts it to H.264/yuv420p so the clip
    plays in the Events UI. Returns True on success.
    """
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", src,
             "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
             "-movflags", "+faststart", dst],
            check=True, capture_output=True,
        )
        return os.path.isfile(dst) and os.path.getsize(dst) > 0
    except Exception as exc:  # ffmpeg missing / encode failed
        logger.warning("H.264 transcode failed (%s); keeping mp4v fallback", exc)
        return False


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
    raw_path = EVIDENCE_DIR / f".raw_{filename}"   # mp4v scratch, transcoded below

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(raw_path), fourcc, fps,
                             output_size)

    if not writer.isOpened():
        logger.error(f"Failed to create video writer: {raw_path}")
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

    # Transcode to browser-playable H.264; fall back to the raw mp4v on failure.
    if _transcode_h264(str(raw_path), str(filepath)):
        try:
            os.remove(raw_path)
        except OSError:
            pass
    else:
        os.replace(raw_path, filepath)

    logger.info(f"Evidence saved: {filepath} ({frame_count} frames, "
                f"{frame_count / fps:.1f}s)")
    return str(filepath)
