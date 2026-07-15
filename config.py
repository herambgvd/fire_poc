"""
Centralized configuration for the Fire & Smoke Detection System.
Settings are persisted to a JSON file and can be updated from the GUI.
"""

import json
import os
from pathlib import Path
from dotenv import load_dotenv

# ── Paths ──────────────────────────────────────────────────────────────────────
APP_DIR = Path(__file__).parent.resolve()
ENV_FILE = APP_DIR / ".env"
SETTINGS_FILE = APP_DIR / "settings.json"
LOGS_DIR = APP_DIR / "logs"
EVIDENCE_DIR = APP_DIR / "evidence"
ALERT_SOUND_FILE = APP_DIR / "alert_sound.mp3"

# Load .env if present
if ENV_FILE.exists():
    load_dotenv(ENV_FILE, override=True)

# ── Default settings ──────────────────────────────────────────────────────────
DEFAULTS = {
    # Model paths (relative to APP_DIR)
    "stage1_model": "mobilenetv3_small_stage1_with_normal.pth",
    "stage2_model": "yolon11_stage2_with_normal.pt",

    # Stage 1 — MobileNetV3-Small classifier
    "classifier_threshold": 0.5,
    "consecutive_frames_required": 3,

    # Stage 2 — YOLO11n detector
    "yolo_confidence": 0.5,
    "yolo_iou": 0.45,

    # Live annotation: continuously draw Stage-2 boxes on the live view (web POC)
    # even in normal mode, so the browser always shows detections. Throttled:
    # run Stage-2 every Nth frame for display (event/cooldown logic is unaffected).
    "live_annotate": True,
    "live_annotate_every": 2,

    # Buffering & Evidence Timing
    "buffer_seconds": 15,
    "max_await_seconds": 10,
    "post_detection_seconds": 5,
    "low_res_width": 320,
    "low_res_height": 240,

    # Alert
    "alert_cooldown_seconds": 60,
    "sound_enabled": True,

    # Email
    "smtp_server": os.getenv("SMTP_SERVER", "smtp.gmail.com"),
    "smtp_port": int(os.getenv("SMTP_PORT", "465")),
    "smtp_email": os.getenv("SMTP_EMAIL", ""),
    "smtp_password": os.getenv("SMTP_PASSWORD", ""),
    "email_recipients": [],

    # Cameras (list of dicts: {"name": "Cam 1", "url": "rtsp://..."} or {"name": "Test", "path": "video.mp4"})
    "cameras": [],

    # Web POC: single RTSP camera URL (or a local video file path for demos)
    "rtsp_url": "",

    # Number of classes (fire/smoke vs normal for this binary model)
    "num_classes": 2,
    "class_names": ["Fire/Smoke", "Normal"],
}


class Settings:
    """Manages application settings with persistence."""

    def __init__(self):
        self._data = dict(DEFAULTS)
        self._load()

    def _load(self):
        if SETTINGS_FILE.exists():
            try:
                with open(SETTINGS_FILE, "r") as f:
                    saved = json.load(f)
                self._data.update(saved)
            except (json.JSONDecodeError, IOError):
                pass  # Fall back to defaults

    def save(self):
        """Persist current settings to disk."""
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(SETTINGS_FILE, "w") as f:
            json.dump(self._data, f, indent=2)

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value

    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, value):
        self._data[key] = value

    @property
    def stage1_path(self) -> Path:
        return APP_DIR / self._data["stage1_model"]

    @property
    def stage2_path(self) -> Path:
        return APP_DIR / self._data["stage2_model"]

    @property
    def data(self):
        return dict(self._data)


# Global singleton
settings = Settings()
