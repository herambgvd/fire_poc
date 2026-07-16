"""Single-camera pipeline runner for the web POC.

Owns the (lazily loaded) Stage-1/Stage-2 models and, while running, one
``CameraSource`` + ``CameraPipeline``. Wires the pipeline's callbacks so that:

  * every processed frame updates ``latest_jpeg`` (what the MJPEG endpoint streams)
  * a confirmed detection captures a snapshot and writes an event row to SQLite

Thread-safe: the pipeline worker thread writes the latest frame / events while
FastAPI request threads read them.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone

import cv2
import numpy as np

from config import settings
from server import store

logger = logging.getLogger("fire.runner")


class PipelineRunner:
    """Runs one camera through the two-stage pipeline for the web UI."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._classifier = None      # Stage1Classifier (lazy)
        self._detector = None        # Stage2Detector (lazy)
        self._source = None          # CameraSource
        self._pipeline = None        # CameraPipeline

        self._latest_jpeg: bytes | None = None
        self._latest_ts: float = 0.0
        self._status_text: str = "Idle"
        self._source_url: str | None = None

        # Snapshot capture: on_alert flags the next frame to be saved as the
        # event's snapshot (so it's the annotated detection frame, not a later one).
        self._want_snapshot = False
        self._pending_snapshot: bytes | None = None

    # ── model loading (heavy; done once, on first start) ────────────────────
    def _ensure_models(self) -> None:
        if self._classifier is not None and self._detector is not None:
            return
        import torch
        from core.stage1_classifier import Stage1Classifier
        from core.stage2_detector import Stage2Detector

        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info("loading models on %s (stage1=%s, stage2=%s)",
                    device, settings.stage1_path, settings.stage2_path)
        self._classifier = Stage1Classifier(
            model_path=str(settings.stage1_path),
            num_classes=int(settings.get("num_classes", 2)),
            device=device,
        )
        self._detector = Stage2Detector(model_path=str(settings.stage2_path), device=device)
        logger.info("models loaded (device=%s)", device)

    @property
    def models_loaded(self) -> bool:
        return self._classifier is not None and self._detector is not None

    # ── lifecycle ───────────────────────────────────────────────────────────
    def start(self, rtsp_url: str | None = None) -> None:
        """(Re)start monitoring on the given RTSP url (or the saved one)."""
        with self._lock:
            if self._pipeline is not None and self._pipeline.is_running:
                raise RuntimeError("already running")

        url = rtsp_url or settings.get("rtsp_url") or ""
        if not url:
            raise ValueError("no RTSP url configured")

        self._ensure_models()

        from camera.camera_source import CameraSource
        from core.pipeline import CameraPipeline

        # A local video file? loop it (handy for demos). RTSP/HTTP: no loop.
        loop = not str(url).lower().startswith(("rtsp://", "http://", "https://"))
        source = CameraSource(source=url, name="Camera 1", loop=loop)
        if not source.open():
            raise RuntimeError(f"cannot open source: {url}")

        pipe = CameraPipeline(
            camera_name="Camera 1",
            classifier=self._classifier,
            detector=self._detector,
            alert_callback=None,   # email disabled in the POC
        )
        pipe.set_source(source)
        pipe.callbacks.on_frame = self._on_frame
        pipe.callbacks.on_status = self._on_status
        pipe.callbacks.on_alert = self._on_alert
        pipe.callbacks.on_event = self._on_event

        with self._lock:
            self._source = source
            self._pipeline = pipe
            self._source_url = url
            self._status_text = "Starting…"
            self._latest_jpeg = None
        pipe.start()
        logger.info("runner started on %s", url)

    def stop(self) -> None:
        with self._lock:
            pipe, source = self._pipeline, self._source
            self._pipeline = self._source = None
            self._status_text = "Idle"
            self._latest_jpeg = None
        if pipe is not None:
            pipe.stop()
        if source is not None:
            source.release()
        logger.info("runner stopped")

    @property
    def is_running(self) -> bool:
        return self._pipeline is not None and self._pipeline.is_running

    def status(self) -> dict:
        with self._lock:
            online = bool(self._source and self._source.is_open())
            fresh = (time.time() - self._latest_ts) < 3.0 if self._latest_ts else False
            return {
                "running": self.is_running,
                "camera_online": online and fresh,
                "models_loaded": self.models_loaded,
                "status_text": self._status_text,
                "source": self._source_url,
            }

    # ── frame access for the MJPEG stream ───────────────────────────────────
    def latest_jpeg(self) -> bytes | None:
        with self._lock:
            return self._latest_jpeg

    # ── pipeline callbacks (run on the worker thread) ───────────────────────
    def _encode(self, frame: np.ndarray) -> bytes | None:
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        return buf.tobytes() if ok else None

    def _on_frame(self, camera: str, frame: np.ndarray) -> None:
        jpeg = self._encode(frame)
        if jpeg is None:
            return
        with self._lock:
            self._latest_jpeg = jpeg
            self._latest_ts = time.time()
            if self._want_snapshot:
                self._pending_snapshot = jpeg
                self._want_snapshot = False

    def _on_status(self, camera: str, text: str) -> None:
        with self._lock:
            self._status_text = text

    def _on_alert(self, camera: str, dtype: str, path: str) -> None:
        # Grab the next processed (annotated) frame as this event's snapshot.
        with self._lock:
            self._want_snapshot = True
            self._pending_snapshot = self._latest_jpeg  # fallback if no next frame

    def _on_event(self, info: dict) -> None:
        """A confirmed detection finished assembling — persist it."""
        try:
            camera = info.get("camera", "Camera 1")
            dtype = info.get("type", "Fire")
            s1 = info.get("stage1") or {}
            s2 = info.get("stage2") or {}
            evidence = info.get("evidence")

            stage1 = float(s1.get("fire")) if s1.get("fire") is not None else None
            boxes = s2.get("boxes") or []
            best = max((b.get("conf", 0.0) for b in boxes), default=None)
            stage2 = float(best) if best is not None else None

            ts = datetime.now(timezone.utc)
            snap_name = None
            with self._lock:
                snap_bytes = self._pending_snapshot
                self._pending_snapshot = None
            if snap_bytes:
                snap_name = f"{ts.strftime('%Y%m%d_%H%M%S')}_{dtype}.jpg"
                (store.SNAPSHOT_DIR).mkdir(parents=True, exist_ok=True)
                with open(store.SNAPSHOT_DIR / snap_name, "wb") as f:
                    f.write(snap_bytes)

            eid = store.add_event(
                camera=camera, type=dtype,
                confidence=stage2, stage1=stage1, stage2=stage2,
                snapshot=snap_name, evidence=evidence, ts=ts.isoformat(),
            )
            logger.info("event #%s recorded (%s, conf=%s)", eid, dtype, stage2)
        except Exception as exc:  # noqa: BLE001 — never let a bad event kill the worker
            logger.error("failed to record event: %s", exc)


# Process-wide singleton used by the FastAPI app.
runner = PipelineRunner()
