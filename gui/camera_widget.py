"""
Camera feed widget — displays a single camera's live video
with status overlay and colored border based on detection state.
"""

import cv2
import numpy as np

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap, QFont
from PyQt6.QtWidgets import (QVBoxLayout, QLabel, QFrame,
                             QHBoxLayout, QSizePolicy)


class CameraWidget(QFrame):
    """Displays a single camera feed with detection status overlay."""

    BORDER_COLORS = {
        "normal": "#3fb950",
        "watching": "#d29922",
        "alert": "#f85149",
    }

    def __init__(self, camera_name: str = "Camera", parent=None):
        super().__init__(parent)
        self.camera_name = camera_name
        self._state = "normal"

        self.setStyleSheet(
            "CameraWidget { background-color: #161b22; "
            "border: 2px solid #3fb950; border-radius: 8px; }")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        # Header
        header = QHBoxLayout()
        self._name_label = QLabel(f"📷 {camera_name}")
        self._name_label.setStyleSheet(
            "font-weight: bold; font-size: 12px; color: #e6edf3; padding: 2px;")
        header.addWidget(self._name_label)

        self._fps_label = QLabel("")
        self._fps_label.setStyleSheet(
            "font-size: 10px; color: #8b949e; padding: 2px;")
        self._fps_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        header.addWidget(self._fps_label)
        layout.addLayout(header)

        # Video display
        self._video_label = QLabel("No feed")
        self._video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._video_label.setMinimumSize(320, 240)
        self._video_label.setSizePolicy(QSizePolicy.Policy.Expanding,
                                         QSizePolicy.Policy.Expanding)
        self._video_label.setStyleSheet(
            "color: #8b949e; font-size: 14px; "
            "background-color: #0d1117; border-radius: 4px;")
        layout.addWidget(self._video_label)

        # Status bar
        self._status_label = QLabel("🟢 Waiting...")
        self._status_label.setStyleSheet(
            "font-size: 11px; color: #8b949e; padding: 3px; "
            "background-color: #21262d; border-radius: 4px;")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._status_label)

    def update_frame(self, bgr_frame: np.ndarray):
        """Update the displayed frame."""
        try:
            rgb = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            bytes_per_line = ch * w
            qimg = QImage(rgb.data, w, h, bytes_per_line,
                          QImage.Format.Format_RGB888).copy()
            label_size = self._video_label.size()
            pixmap = QPixmap.fromImage(qimg).scaled(
                label_size, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
            self._video_label.setPixmap(pixmap)
        except Exception:
            pass

    def update_status(self, status_text: str):
        """Update detection status text and border color."""
        self._status_label.setText(status_text)

        if "CONFIRMED" in status_text or "🔴" in status_text:
            self._set_state("alert")
        elif "Escalated" in status_text or "⚠️" in status_text or "🟡" in status_text:
            self._set_state("watching")
        else:
            self._set_state("normal")

    def _set_state(self, state: str):
        if state == self._state:
            return
        self._state = state
        color = self.BORDER_COLORS.get(state, "#3fb950")
        self.setStyleSheet(
            f"CameraWidget {{ background-color: #161b22; "
            f"border: 2px solid {color}; border-radius: 8px; }}")

    def set_fps(self, fps: float):
        self._fps_label.setText(f"{fps:.1f} FPS")
