"""
Rolling video buffer for evidence capture.

Per camera:
  - Low-res circular buffer (last N seconds) runs continuously in RAM.
  - On Stage 1 escalation → lo-res buffer is snapshotted, hi-res recording begins.
  - During recording → Stage 2 annotated frames are pushed to hi-res.
  - On finalize → snapshotted lo-res buffer + hi-res annotated frames are returned.

Frames are stored as compressed JPEG bytes to save memory.
"""

import logging
import time
from collections import deque

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class BufferManager:
    """Manages low-res circular buffer + hi-res recording per camera."""

    def __init__(self, buffer_seconds: int = 15,
                 low_res_size: tuple = (320, 240),
                 fps_estimate: float = 15.0):
        self.buffer_seconds = buffer_seconds
        self.low_res_size = low_res_size
        self.fps = fps_estimate

        max_frames = int(buffer_seconds * fps_estimate)
        self._lo_buffer = deque(maxlen=max_frames)  # (timestamp, jpeg_bytes)

        self._hi_frames = []         # list of (timestamp, bgr_ndarray)
        self._lo_snapshot = []       # snapshot of lo_buffer taken at escalation
        self._recording_hi = False

        logger.debug(f"Buffer init: {buffer_seconds}s @ ~{fps_estimate} FPS "
                     f"= max {max_frames} lo-res frames")

    # ──────────────────────────────────────────────────────────────────────────
    def push_frame(self, bgr_frame: np.ndarray):
        """Push to the low-res circular buffer only."""
        small = cv2.resize(bgr_frame, self.low_res_size)
        _, jpeg = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 60])
        self._lo_buffer.append((time.time(), jpeg.tobytes()))

    def push_hi_frame(self, bgr_frame: np.ndarray):
        """Push a frame to the hi-res recording buffer (Stage 2 annotated)."""
        if self._recording_hi:
            self._hi_frames.append((time.time(), bgr_frame.copy()))

    def start_hi_res_recording(self):
        """
        Begin hi-res recording.  Snapshots the current lo-res buffer
        so it can be returned later even after the circular buffer overwrites.
        """
        if not self._recording_hi:
            self._recording_hi = True
            self._hi_frames.clear()
            # Snapshot the pre-detection buffer at this moment
            self._lo_snapshot = list(self._lo_buffer)
            logger.debug(f"Hi-res recording started "
                         f"(snapshotted {len(self._lo_snapshot)} lo-res frames)")

    def stop_hi_res_recording(self, keep: bool = False):
        """
        Stop hi-res recording.
        If keep=True, returns (lo_snapshot, hi_frames).
          lo_snapshot: list of (timestamp, jpeg_bytes) from BEFORE escalation
          hi_frames:   list of (timestamp, bgr_ndarray) recorded AFTER escalation
        If keep=False, discards everything.
        """
        self._recording_hi = False
        if keep:
            lo = list(self._lo_snapshot)
            hi = list(self._hi_frames)
            self._hi_frames.clear()
            self._lo_snapshot.clear()
            logger.debug(f"Hi-res recording kept: {len(lo)} lo + {len(hi)} hi frames")
            return lo, hi
        else:
            self._hi_frames.clear()
            self._lo_snapshot.clear()
            logger.debug("Hi-res recording discarded")
            return None, None

    @property
    def is_recording_hi(self):
        return self._recording_hi
