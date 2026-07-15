"""
Structured logging for the Fire & Smoke Detection System.
- Rotating file log (logs/detection.log)
- Separate detection event CSV log (logs/detections.csv)
- Console output
"""

import csv
import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config import LOGS_DIR

# The GUI log handler is only available in the desktop (PyQt) build. In the
# web/headless build there is no GUI, so import it best-effort and fall back to
# None — setup_logging() skips it when unavailable.
try:
    from gui.log_handler import gui_log_handler
except Exception:  # PyQt6 not installed / no GUI
    gui_log_handler = None


def setup_logging(level=logging.INFO):
    """Configure root logger with file + console handlers."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(level)

    # Prevent duplicate handlers on re-init
    if root.handlers:
        return

    fmt = logging.Formatter(
        "[%(asctime)s] [%(levelname)-8s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # ── File handler (rotating, 10 MB, 5 backups) ──
    fh = RotatingFileHandler(
        LOGS_DIR / "detection.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    fh.setLevel(level)
    fh.setFormatter(fmt)
    root.addHandler(fh)

    # ── Console handler (Terminal output disabled per user request) ──
    # ch = logging.StreamHandler()
    # ch.setLevel(level)
    # ch.setFormatter(fmt)
    # root.addHandler(ch)

    # ── GUI handler (Routes logs to dashboard) — desktop build only ──
    if gui_log_handler is not None:
        gui_log_handler.setLevel(level)
        root.addHandler(gui_log_handler)


class DetectionEventLogger:
    """
    Writes detection events to a CSV file for post-analysis.
    Columns: timestamp, camera, stage1_fire, stage1_smoke, stage2_fire,
             stage2_smoke, confirmed, evidence_path
    """

    CSV_HEADER = [
        "timestamp", "camera", "stage1_fire_prob", "stage1_smoke_prob",
        "stage2_fire", "stage2_smoke", "confirmed", "evidence_path",
    ]

    def __init__(self):
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        self.csv_path = LOGS_DIR / "detections.csv"
        self._ensure_header()

    def _ensure_header(self):
        if not self.csv_path.exists():
            with open(self.csv_path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(self.CSV_HEADER)

    def log_event(self, camera_name, stage1_fire, stage1_smoke,
                  stage2_fire=None, stage2_smoke=None,
                  confirmed=False, evidence_path=""):
        try:
            with open(self.csv_path, "a", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    datetime.now().isoformat(),
                    camera_name,
                    f"{stage1_fire:.3f}",
                    f"{stage1_smoke:.3f}",
                    stage2_fire if stage2_fire is not None else "",
                    stage2_smoke if stage2_smoke is not None else "",
                    confirmed,
                    evidence_path,
                ])
        except IOError:
            logging.getLogger(__name__).error("Failed to write detection CSV")


# Global singleton
event_logger = DetectionEventLogger()
