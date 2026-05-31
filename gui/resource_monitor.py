"""
Live CPU and RAM gauge widgets using custom QPainter circular arcs.
Tracks THIS APPLICATION's resource usage, not the whole system.
"""

import os
import psutil
from collections import deque

from PyQt6.QtCore import Qt, QTimer, QRectF
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QLinearGradient
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QFrame

# Get handle to our own process once at import time
_PROCESS = psutil.Process(os.getpid())


class CircularGauge(QWidget):
    """Animated circular arc gauge for CPU or RAM."""

    def __init__(self, label: str = "CPU", unit: str = "%",
                 max_val: float = 100.0, color: str = "#58a6ff",
                 parent=None):
        super().__init__(parent)
        self.label_text = label
        self.unit = unit
        self.max_val = max_val
        self.color = QColor(color)
        self._value = 0.0
        self._peak = 0.0
        self._sum = 0.0
        self._count = 0
        self._warmup_remaining = 5  # ignore first N updates for peak tracking
        self.setMinimumSize(130, 180)
        self.setMaximumSize(180, 220)

    def set_value(self, value: float):
        self._value = min(value, self.max_val)
        if self._warmup_remaining > 0:
            self._warmup_remaining -= 1
        else:
            self._peak = max(self._peak, self._value)
            self._sum += self._value
            self._count += 1
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        size = min(w, h - 35)
        cx, cy = w // 2, size // 2 + 5
        radius = size // 2 - 12

        rect = QRectF(cx - radius, cy - radius, radius * 2, radius * 2)

        # ── Background arc ──
        bg_pen = QPen(QColor("#21262d"), 10, Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap)
        painter.setPen(bg_pen)
        painter.drawArc(rect, 225 * 16, -270 * 16)

        # ── Value arc ──
        pct = self._value / self.max_val if self.max_val else 0
        sweep = int(-270 * pct * 16)

        # Dynamic color: green → yellow → red
        if pct < 0.5:
            arc_color = QColor("#3fb950")
        elif pct < 0.75:
            arc_color = QColor("#d29922")
        else:
            arc_color = QColor("#f85149")

        val_pen = QPen(arc_color, 10, Qt.PenStyle.SolidLine,
                       Qt.PenCapStyle.RoundCap)
        painter.setPen(val_pen)
        painter.drawArc(rect, 225 * 16, sweep)

        # ── Center text: value ──
        painter.setPen(QColor("#e6edf3"))
        if self.unit == "MB":
            font = QFont("Segoe UI", 14, QFont.Weight.Bold)
            val_text = f"{self._value:.0f}"
        elif self.unit == "%":
            font = QFont("Segoe UI", 18, QFont.Weight.Bold)
            val_text = f"{self._value:.0f}"
        else:
            font = QFont("Segoe UI", 18, QFont.Weight.Bold)
            val_text = f"{self._value:.1f}"
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter,
                         f"{val_text}{self.unit}")

        # ── Bottom label ──
        painter.setPen(QColor("#8b949e"))
        font2 = QFont("Segoe UI", 10)
        painter.setFont(font2)
        label_rect = QRectF(0, size + 5, w, 18)
        painter.drawText(label_rect, Qt.AlignmentFlag.AlignHCenter, self.label_text)

        # ── Peak label ──
        peak_text = f"Peak: {self._peak:.1f}{self.unit}"
        if self.unit == "%":
            peak_text = f"Peak: {self._peak:.0f}{self.unit}"
        peak_rect = QRectF(0, size + 20, w, 16)
        painter.setFont(QFont("Segoe UI", 9))
        painter.drawText(peak_rect, Qt.AlignmentFlag.AlignHCenter, peak_text)

        # ── Avg label ──
        avg_val = (self._sum / self._count) if self._count > 0 else 0.0
        avg_text = f"Avg: {avg_val:.1f}{self.unit}"
        if self.unit == "%":
            avg_text = f"Avg: {avg_val:.0f}{self.unit}"
        avg_rect = QRectF(0, size + 35, w, 16)
        painter.drawText(avg_rect, Qt.AlignmentFlag.AlignHCenter, avg_text)

        painter.end()


class ResourceMonitorWidget(QFrame):
    """CPU + RAM monitor for THIS APPLICATION (not system-wide)."""

    # RAM gauge max in MB — a reasonable ceiling for this app
    RAM_MAX_MB = 2048

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("class", "card")
        self.setStyleSheet("""
            ResourceMonitorWidget {
                background-color: #161b22;
                border: 1px solid #30363d;
                border-radius: 8px;
            }
        """)

        self._history_len = 60  # seconds of history
        self._cpu_history = deque(maxlen=self._history_len)
        self._ram_history = deque(maxlen=self._history_len)

        # Prime the process CPU measurement (first call always returns 0)
        _PROCESS.cpu_percent(interval=None)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        title = QLabel("⚡ App Resource Usage")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #e3803b;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Gauges
        gauge_layout = QHBoxLayout()
        self.cpu_gauge = CircularGauge("App CPU", "%", 100, "#58a6ff")
        self.ram_gauge = CircularGauge("App RAM", "MB",
                                       self.RAM_MAX_MB, "#3fb950")
        gauge_layout.addWidget(self.cpu_gauge)
        gauge_layout.addWidget(self.ram_gauge)
        layout.addLayout(gauge_layout)

        # Sparkline
        self.sparkline = SparklineWidget()
        layout.addWidget(self.sparkline)

        # ── Timer: update every 1 second ──
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update)
        self._timer.start(1000)

        # Initial sample
        self._update()

    def _update(self):
        try:
            # Process-level CPU normalized across all cores to match Task Manager
            # psutil returns >100% for multi-threaded apps, so we divide by cpu_count
            cpu = min(_PROCESS.cpu_percent(interval=None) / psutil.cpu_count(), 100.0)

            # Process-level RAM (RSS = resident set size)
            ram_mb = _PROCESS.memory_info().rss / (1024 * 1024)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            cpu, ram_mb = 0.0, 0.0

        self.cpu_gauge.set_value(cpu)
        self.ram_gauge.set_value(ram_mb)

        self._cpu_history.append(cpu)
        # Normalise RAM to 0–100 for sparkline rendering
        self._ram_history.append(min(ram_mb / self.RAM_MAX_MB * 100, 100))

        self.sparkline.set_data(list(self._cpu_history),
                                list(self._ram_history))


class SparklineWidget(QWidget):
    """Mini sparkline chart for CPU/RAM history."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(50)
        self.setMaximumHeight(60)
        self._cpu_data = []
        self._ram_data = []

    def set_data(self, cpu: list, ram: list):
        self._cpu_data = cpu
        self._ram_data = ram
        self.update()

    def paintEvent(self, event):
        if not self._cpu_data:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        margin = 4

        # Draw CPU sparkline
        self._draw_line(painter, self._cpu_data, QColor("#58a6ff"),
                        w, h, margin)
        # Draw RAM sparkline
        self._draw_line(painter, self._ram_data, QColor("#3fb950"),
                        w, h, margin)

        # Legend
        painter.setPen(QColor("#8b949e"))
        painter.setFont(QFont("Segoe UI", 8))
        painter.drawText(margin, h - 2, "— CPU  — RAM")

        painter.end()

    def _draw_line(self, painter, data, color, w, h, margin):
        if len(data) < 2:
            return
        pen = QPen(color, 1.5)
        painter.setPen(pen)

        n = len(data)
        x_step = (w - 2 * margin) / max(n - 1, 1)

        for i in range(1, n):
            x0 = margin + (i - 1) * x_step
            x1 = margin + i * x_step
            y0 = h - margin - (data[i - 1] / 100.0) * (h - 2 * margin)
            y1 = h - margin - (data[i] / 100.0) * (h - 2 * margin)
            painter.drawLine(int(x0), int(y0), int(x1), int(y1))
