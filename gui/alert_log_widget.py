"""
Alert log widget — scrollable table of detection events.
"""

from datetime import datetime
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (QFrame, QVBoxLayout, QLabel, QTableWidget,
                             QTableWidgetItem, QHeaderView, QPushButton,
                             QHBoxLayout, QFileDialog)


class AlertLogWidget(QFrame):
    """
    Scrollable table showing all detection events with color coding.
    This widget maintains a history of all detections, their types, and the confidence
    scores from Stage 1 and Stage 2 models.
    """

    COLUMNS = ["Time", "Camera", "Type", "S1 Fire", "S1 Smoke",
               "S2 Result", "Evidence"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            AlertLogWidget {
                background-color: #161b22;
                border: 1px solid #30363d;
                border-radius: 8px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # Header
        header = QHBoxLayout()
        title = QLabel("📋 Detection Log")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #e3803b;")
        header.addWidget(title)

        self._count_label = QLabel("0 events")
        self._count_label.setStyleSheet("color: #8b949e; font-size: 11px;")
        header.addStretch()
        header.addWidget(self._count_label)

        export_btn = QPushButton("Export CSV")
        export_btn.setFixedHeight(28)
        export_btn.clicked.connect(self._export_csv)
        header.addWidget(export_btn)

        clear_btn = QPushButton("Clear")
        clear_btn.setFixedHeight(28)
        clear_btn.clicked.connect(self._clear)
        header.addWidget(clear_btn)
        layout.addLayout(header)

        # Table
        self.table = QTableWidget(0, len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

    def add_event(self, event: dict):
        """
        Add a detection event row to the table.
        This is typically called by a signal when the pipeline finishes processing an event.
        """
        row = self.table.rowCount()
        self.table.insertRow(row)

        ts = datetime.fromtimestamp(event.get("timestamp", 0))
        s1 = event.get("stage1", {})
        s2 = event.get("stage2") or {}
        det_type = event.get("type", "Unknown")

        values = [
            ts.strftime("%H:%M:%S"),
            event.get("camera", "—"),
            det_type,
            f"{s1.get('fire', 0):.2f}",
            f"{s1.get('smoke', 0):.2f}",
            "✅ Confirmed" if s2.get("confirmed") else "❌ Rejected",
            event.get("evidence", "—") or "—",
        ]

        # Row color is determined by the detection type
        # Red for fire, Orange for smoke
        if det_type == "Fire":
            bg = QColor(248, 81, 73, 40)
        elif det_type == "Smoke":
            bg = QColor(227, 128, 59, 40)
        else:
            bg = QColor(0, 0, 0, 0)

        for col, val in enumerate(values):
            item = QTableWidgetItem(str(val))
            item.setBackground(bg)
            self.table.setItem(row, col, item)

        self.table.scrollToBottom()
        self._count_label.setText(f"{self.table.rowCount()} events")

    def _clear(self):
        self.table.setRowCount(0)
        self._count_label.setText("0 events")

    def _export_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export CSV", "detection_log.csv", "CSV Files (*.csv)")
        if not path:
            return
        import csv
        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(self.COLUMNS)
            for row in range(self.table.rowCount()):
                writer.writerow([
                    self.table.item(row, col).text()
                    for col in range(self.table.columnCount())
                ])
