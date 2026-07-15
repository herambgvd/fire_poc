"""
Two-stage cascade pipeline orchestrator.

Runs in a dedicated thread per camera:
  1) Reads frames from camera source
  2) Stage 1: MobileNetV3-Small classifier on every frame
  3) Tracks consecutive fire/smoke flags
  4) On escalation → Stage 2 takes over the live stream:
     a) Snapshot the lo-res buffer
     b) Run Stage 2 on every live frame (detection + bounding boxes)
     c) If Stage 2 confirms → ALERT fires immediately + record proof
     d) Continue recording for POST_DETECTION_SECONDS after confirmation
     e) If no confirmation within MAX_AWAIT_SECONDS → discard, return to Stage 1
  5) On finalize → background thread:
     a) Annotate buffer frames through Stage 2 (detection + bboxes)
     b) Assemble evidence MP4 (annotated buffer + annotated recording)
     c) Send email alert with evidence

Emits Qt signals for GUI updates.
"""

import logging
import threading
import time

import cv2
import numpy as np

from config import settings
from logging_config import event_logger
from core.stage1_classifier import Stage1Classifier
from core.stage2_detector import Stage2Detector
from core.buffer_manager import BufferManager
from core.evidence import assemble_evidence

logger = logging.getLogger(__name__)


class PipelineCallbacks:
    """Plain callback holder — the pipeline calls these to report activity.

    Framework-agnostic (no PyQt): the web server assigns real callbacks; each
    defaults to a no-op so the pipeline runs headless without any consumer wired.
    """

    def __init__(self):
        self.on_frame = lambda camera, frame: None    # (camera_name, bgr_frame)
        self.on_status = lambda camera, text: None     # (camera_name, status_text)
        self.on_event = lambda info: None              # (detection_info_dict)
        self.on_alert = lambda camera, dtype, path: None  # (camera_name, type, evidence_path)


class CameraPipeline:
    """Cascade pipeline for a single camera feed."""

    def __init__(self, camera_name: str,
                 classifier: Stage1Classifier,
                 detector: Stage2Detector,
                 alert_callback=None):
        self.camera_name = camera_name
        self.classifier = classifier
        self.detector = detector
        self.alert_callback = alert_callback

        self.callbacks = PipelineCallbacks()

        # State
        self._running = False
        self._thread = None
        self._source = None
        self._fire_streak = 0
        self._smoke_streak = 0

        # Buffer
        self.buffer = BufferManager(
            buffer_seconds=settings["buffer_seconds"],
            low_res_size=(settings["low_res_width"], settings["low_res_height"]),
        )

        # Cooldown
        self._last_alert_time = 0

        # Recording state
        self._recording_active = False
        self._recording_start = 0.0
        # Sub-state: waiting for Stage 2 confirmation vs recording proof
        self._awaiting_confirmation = True
        self._proof_start = 0.0
        self._recording_det_type = ""
        self._recording_last_s1 = None
        self._recording_last_s2 = None

        # Lock to prevent concurrent Stage 2 usage
        self._detector_lock = threading.Lock()

    # ──────────────────────────────────────────────────────────────────────────
    def set_source(self, source):
        self._source = source

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True,
                                        name=f"Pipeline-{self.camera_name}")
        self._thread.start()
        logger.info(f"[{self.camera_name}] Pipeline started")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info(f"[{self.camera_name}] Pipeline stopped")

    # ──────────────────────────────────────────────────────────────────────────
    def _annotate_and_assemble(self, lo_jpeg_frames, hi_frames,
                                det_type, s1, s2):
        """
        Background thread: annotate buffer frames via Stage 2, assemble
        evidence MP4, and send email alert with evidence attached.
        This runs in the background so it doesn't block the live camera feed.
        """
        try:
            self.callbacks.on_status(
                self.camera_name, "⏳ Processing evidence...")

            # Annotate pre-detection buffer frames with Stage 2
            annotated_pre = []
            total = len(lo_jpeg_frames)
            logger.info(f"[{self.camera_name}] Running Stage 2 on {total} buffer frames...")

            for ts, jpeg_bytes in lo_jpeg_frames:
                arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
                frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                if frame is None:
                    continue

                # Use a lock when calling the detector in the background to avoid 
                # race conditions if the main thread tries to use it simultaneously.
                with self._detector_lock:
                    s2_result = self.detector.predict(
                        frame,
                        conf=settings["yolo_confidence"],
                        iou=settings["yolo_iou"],
                    )

                if s2_result["confirmed"]:
                    annotated_pre.append((ts, s2_result["annotated"]))
                else:
                    annotated_pre.append((ts, frame))

            logger.info(f"[{self.camera_name}] Buffer processing done: "
                        f"{len(annotated_pre)} frames")

            # Assemble evidence MP4
            evidence_path = assemble_evidence(
                annotated_pre, hi_frames, self.camera_name, det_type)

            logger.info(
                f"[{self.camera_name}] Evidence saved: {evidence_path} "
                f"({len(annotated_pre)} pre + {len(hi_frames)} post frames)")

            # Emit detection event for alert log widget
            self.callbacks.on_event({
                "camera": self.camera_name,
                "type": det_type,
                "stage1": s1,
                "stage2": s2,
                "evidence": evidence_path,
                "timestamp": time.time(),
            })

            # Send email alert with evidence attached
            if self.alert_callback:
                self.alert_callback(self.camera_name, det_type, None, evidence_path)

            self.callbacks.on_status(
                self.camera_name, "✅ Evidence saved")

        except Exception as e:
            logger.error(f"[{self.camera_name}] Evidence assembly failed: {e}")
            self.callbacks.on_status(
                self.camera_name, f"❌ Evidence error: {e}")

    # ──────────────────────────────────────────────────────────────────────────
    def _finalize_recording(self):
        """
        Called after proof recording completes.
        Grabs all frames and hands off to background thread for assembly.
        Pipeline returns to Stage 1 immediately.
        """
        det_type = self._recording_det_type or "Unknown"
        s1 = self._recording_last_s1
        s2 = self._recording_last_s2

        lo_jpeg_frames, hi_frames = self.buffer.stop_hi_res_recording(keep=True)
        lo_jpeg_frames = lo_jpeg_frames or []
        hi_frames = hi_frames or []

        # Hand off to background thread
        bg = threading.Thread(
            target=self._annotate_and_assemble,
            args=(lo_jpeg_frames, hi_frames, det_type, s1, s2),
            daemon=True,
            name=f"Evidence-{self.camera_name}",
        )
        bg.start()

        # Reset state — pipeline resumes Stage 1 immediately
        self._recording_active = False
        self._awaiting_confirmation = True
        self._recording_det_type = ""
        self._recording_last_s1 = None
        self._recording_last_s2 = None
        self._fire_streak = 0
        self._smoke_streak = 0

    # ──────────────────────────────────────────────────────────────────────────
    def _run(self):
        """Main pipeline loop."""
        try:
            while self._running:
                loop_start_time = time.time()
                if self._source is None or not self._source.is_open():
                    time.sleep(0.5)
                    continue

                ret, frame = self._source.read()
                if not ret or frame is None:
                    time.sleep(0.05)
                    continue

                # Always push raw frame to lo-res circular buffer
                self.buffer.push_frame(frame)

                # ══════════════════════════════════════════════════════════════
                # RECORDING MODE — Stage 2 on every live frame
                # ══════════════════════════════════════════════════════════════
                if self._recording_active:

                    # Run Stage 2 on every live frame. This is computationally expensive,
                    # which is why it is only active after Stage 1 escalates.
                    with self._detector_lock:
                        s2 = self.detector.predict(
                            frame,
                            conf=settings["yolo_confidence"],
                            iou=settings["yolo_iou"],
                        )

                    # Store frame in hi-res buffer (annotated if detected)
                    if s2["confirmed"]:
                        self.buffer.push_hi_frame(s2["annotated"])
                        display_frame = s2["annotated"]
                    else:
                        self.buffer.push_hi_frame(frame)
                        display_frame = frame

                    # ── SUB-STATE: Awaiting first Stage 2 confirmation ──
                    if self._awaiting_confirmation:
                        max_await = settings.get("max_await_seconds", 10)
                        elapsed = time.time() - self._recording_start
                        remaining = max(0, max_await - elapsed)

                        if s2["confirmed"]:
                            # ★ FIRST DETECTION — alert fires NOW ★
                            det_type = "Fire" if s2["fire"] else "Smoke"
                            self._awaiting_confirmation = False
                            self._proof_start = time.time()
                            self._recording_det_type = det_type
                            self._recording_last_s2 = s2
                            post_detect = settings.get("post_detection_seconds", 5)

                            logger.critical(
                                f"[{self.camera_name}] {det_type} CONFIRMED by Stage 2 "
                                f"({len(s2['boxes'])} detections) — "
                                f"recording {post_detect}s of proof")

                            # Immediate alert (sound + notification)
                            self.callbacks.on_alert(
                                self.camera_name, det_type, "")

                            self.callbacks.on_status(
                                self.camera_name,
                                f"🔴 {det_type} DETECTED — Recording proof "
                                f"({post_detect}s)")

                            # Log event
                            event_logger.log_event(
                                camera_name=self.camera_name,
                                stage1_fire=self._recording_last_s1["fire"],
                                stage1_smoke=self._recording_last_s1["smoke"],
                                stage2_fire=s2["fire"],
                                stage2_smoke=s2["smoke"],
                                confirmed=True,
                            )

                        elif elapsed >= max_await:
                            # Timeout — Stage 2 never confirmed
                            logger.info(
                                f"[{self.camera_name}] Stage 2 did not confirm "
                                f"within {max_await}s — discarding")
                            self.buffer.stop_hi_res_recording(keep=False)
                            self._recording_active = False
                            self._awaiting_confirmation = True
                            self._fire_streak = 0
                            self._smoke_streak = 0
                            self.callbacks.on_status(
                                self.camera_name,
                                "✅ Stage 2 did not confirm — Resuming")
                        else:
                            self.callbacks.on_status(
                                self.camera_name,
                                f"⚠️ Stage 2 scanning ({remaining:.0f}s)")

                    # ── SUB-STATE: Recording proof after confirmation ──
                    else:
                        post_detect = settings.get("post_detection_seconds", 5)
                        proof_elapsed = time.time() - self._proof_start
                        remaining = max(0, post_detect - proof_elapsed)

                        # Update last s2 if still detecting
                        if s2["confirmed"]:
                            self._recording_last_s2 = s2

                        self.callbacks.on_status(
                            self.camera_name,
                            f"🔴 {self._recording_det_type} — Proof ({remaining:.0f}s)")

                        if proof_elapsed >= post_detect:
                            self._finalize_recording()

                    self.callbacks.on_frame(self.camera_name, display_frame)
                    time.sleep(0.01)
                    continue

                # ══════════════════════════════════════════════════════════════
                # NORMAL MODE — Stage 1 classification
                # ══════════════════════════════════════════════════════════════
                thresh = settings["classifier_threshold"]
                # Run the lightweight Stage 1 classifier on the current frame
                s1 = self.classifier.predict(frame)
                fire_flag, smoke_flag = self.classifier.is_triggered(s1, thresh)

                # Keep track of how many consecutive frames triggered Stage 1
                self._fire_streak = self._fire_streak + 1 if fire_flag else 0
                self._smoke_streak = self._smoke_streak + 1 if smoke_flag else 0

                required = settings["consecutive_frames_required"]
                escalate = (self._fire_streak >= required or
                            self._smoke_streak >= required)

                display_frame = frame.copy()

                if escalate:
                    now = time.time()
                    cooldown = settings["alert_cooldown_seconds"]
                    if now - self._last_alert_time >= cooldown:
                        self._last_alert_time = now

                        # Snapshot buffer + start hi-res recording
                        self.buffer.start_hi_res_recording()
                        self._recording_active = True
                        self._recording_start = time.time()
                        self._awaiting_confirmation = True
                        self._recording_last_s1 = s1

                        self.callbacks.on_status(
                            self.camera_name,
                            "⚠️ Stage 1 Escalated — Stage 2 scanning")
                        logger.warning(
                            f"[{self.camera_name}] Stage 1 escalated: "
                            f"fire={self._fire_streak}, smoke={self._smoke_streak}")

                        event_logger.log_event(
                            camera_name=self.camera_name,
                            stage1_fire=s1["fire"],
                            stage1_smoke=s1["smoke"],
                            stage2_fire=0.0,
                            stage2_smoke=0.0,
                            confirmed=False,
                        )
                    else:
                        self._fire_streak = 0
                        self._smoke_streak = 0
                        self.callbacks.on_status(
                            self.camera_name, "🟡 Alert cooldown active")
                else:
                    status = "🟢 Normal"
                    if self._fire_streak > 0 or self._smoke_streak > 0:
                        status = (f"🟡 Monitoring (fire: {self._fire_streak}/"
                                  f"{required}, smoke: {self._smoke_streak}/{required})")
                    self.callbacks.on_status(self.camera_name, status)

                self.callbacks.on_frame(self.camera_name, display_frame)
                
                # Throttle background thread to max ~30 FPS to prevent overwhelming the GUI event queue
                # which causes massive memory leaks when dealing with local fast-reading videos.
                elapsed = time.time() - loop_start_time
                if elapsed < 0.033:
                    time.sleep(0.033 - elapsed)
                else:
                    time.sleep(0.001)

        except RuntimeError:
            pass

    @property
    def is_running(self):
        return self._running
