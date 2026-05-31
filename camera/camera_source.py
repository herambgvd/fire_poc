"""
Camera source abstraction.
Supports:
  - IP cameras (RTSP / HTTP URL)
  - Local webcam (device index)
  - Test mode (local video file, loops on completion)

Frame grabbing runs in a background thread with the latest frame
always available (no queue backlog).
"""

import logging
import threading
import time

import cv2

logger = logging.getLogger(__name__)


class CameraSource:
    """Thread-safe video source that always provides the latest frame."""

    def __init__(self, source, name: str = "Camera",
                 loop: bool = False):
        """
        Args:
            source: RTSP/HTTP URL string, device index (int), or file path
            name: Human-readable camera name
            loop: If True, loop the video when it ends (for test mode)
        """
        self.source = source
        self.name = name
        self.loop = loop

        self._cap = None
        self._frame = None
        self._ret = False
        self._lock = threading.Lock()
        self._running = False
        self._thread = None
        self._fps = 15.0

    def open(self) -> bool:
        """Open the video source."""
        try:
            if isinstance(self.source, int):
                self._cap = cv2.VideoCapture(self.source, cv2.CAP_DSHOW)
            else:
                self._cap = cv2.VideoCapture(self.source)

            if not self._cap.isOpened():
                logger.error(f"[{self.name}] Cannot open source: {self.source}")
                return False

            self._fps = self._cap.get(cv2.CAP_PROP_FPS) or 15.0
            w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            logger.info(f"[{self.name}] Opened: {self.source} "
                        f"({w}x{h} @ {self._fps:.1f} FPS)")

            self._running = True
            self._thread = threading.Thread(target=self._grab_loop, daemon=True,
                                            name=f"Grab-{self.name}")
            self._thread.start()
            return True

        except Exception as e:
            logger.error(f"[{self.name}] Open failed: {e}")
            return False

    def _grab_loop(self):
        """Background thread: continuously grab the latest frame."""
        delay = max(1.0 / self._fps - 0.005, 0.001)
        while self._running:
            if self._cap is None or not self._cap.isOpened():
                time.sleep(0.5)
                continue

            ret, frame = self._cap.read()

            if not ret:
                if self.loop:
                    # Restart from beginning
                    self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    logger.debug(f"[{self.name}] Video looped")
                    continue
                else:
                    logger.info(f"[{self.name}] Stream ended")
                    with self._lock:
                        self._ret = False
                    break

            with self._lock:
                self._frame = frame
                self._ret = True

            time.sleep(delay)

    def read(self):
        """Return the latest frame (thread-safe)."""
        with self._lock:
            if self._ret and self._frame is not None:
                return True, self._frame.copy()
            return False, None

    def is_open(self) -> bool:
        return self._cap is not None and self._cap.isOpened() and self._running

    @property
    def fps(self):
        return self._fps

    def release(self):
        """Stop grabbing and release the capture."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
        if self._cap:
            self._cap.release()
        logger.info(f"[{self.name}] Released")
