"""
Main dashboard window — the primary UI of the Fire & Smoke Detection System.

Layout:
  ┌──────────────────────────────────────────────────────┐
  │  Title Bar  │  Clock  │  System Status   │  Buttons │
  ├──────────────────────────┬───────────────────────────┤
  │                          │  Resource Monitors        │
  │    Camera Feeds Grid     │  (CPU / RAM gauges)       │
  │    (1-3 cameras)         │                           │
  │                          │  System Logs Console      │
  ├──────────────────────────┴───────────────────────────┤
  │  Alert History (scrollable table)                    │
  └──────────────────────────────────────────────────────┘
"""

import logging
import time

import numpy as np
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QSplitter, QFrame, QGridLayout, QGroupBox,
    QFileDialog, QMessageBox, QScrollArea,
    QStatusBar, QApplication,
)

from config import settings, APP_DIR
from gui.styles import DARK_STYLESHEET
from gui.camera_widget import CameraWidget
from gui.resource_monitor import ResourceMonitorWidget
from gui.alert_log_widget import AlertLogWidget
from gui.settings_dialog import SettingsDialog

from gui.log_handler import gui_log_handler
from PyQt6.QtWidgets import QPlainTextEdit
from PyQt6.QtGui import QTextCursor, QColor, QTextCharFormat

# NOTE: Heavy ML imports (torch, ultralytics) are lazy-loaded inside
# _start_monitoring() to keep idle RAM at ~80 MB instead of ~400 MB.

logger = logging.getLogger(__name__)


class Dashboard(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("🔥 Fire & Smoke Detection System")
        self.setMinimumSize(1200, 750)
        # State
        self._running = False
        self._classifier = None
        self._detector = None
        self._camera_mgr = None
        self._alert_mgr = None   # lazy-created on first Start
        self._camera_widgets: dict[str, CameraWidget] = {}

        self.setStyleSheet(DARK_STYLESHEET)
        self._build_ui()
        self._start_clock()
        self._setup_tray_icon()
        self.showMaximized()
        
        # Connect log handler
        gui_log_handler.signals.new_log.connect(self._append_log)

        logger.info("Dashboard initialized")

    # ══════════════════════════════════════════════════════════════════════════
    # UI CONSTRUCTION
    # ══════════════════════════════════════════════════════════════════════════

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(10, 6, 10, 6)
        root.setSpacing(6)

        # ── TOP BAR ──
        root.addLayout(self._build_top_bar())

        # ── MAIN CONTENT (splitter: cameras+sidebar | log) ──
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Upper section: cameras + sidebar
        upper = QWidget()
        upper_layout = QHBoxLayout(upper)
        upper_layout.setContentsMargins(0, 0, 0, 0)
        upper_layout.setSpacing(8)

        # Camera grid
        self._cam_container = QWidget()
        self._cam_grid = QGridLayout(self._cam_container)
        self._cam_grid.setSpacing(6)
        upper_layout.addWidget(self._cam_container, stretch=3)

        # Sidebar (scrollable)
        sidebar_inner = QWidget()
        sidebar = QVBoxLayout(sidebar_inner)
        sidebar.setSpacing(8)
        sidebar.setContentsMargins(0, 0, 0, 0)

        # Resource Monitor Panel
        self._resource_monitor = ResourceMonitorWidget()
        res_group = QGroupBox("📊 System Resources")
        res_group_layout = QVBoxLayout(res_group)
        res_group_layout.addWidget(self._resource_monitor)
        sidebar.addWidget(res_group)

        # System Console Panel
        self._console = QPlainTextEdit()
        self._console.setReadOnly(True)
        self._console.setMaximumBlockCount(1000)  # Prevent infinite memory growth
        self._console.setStyleSheet("QPlainTextEdit { font-family: Consolas; font-size: 11px; background-color: #0d1117; color: #c9d1d9; border: 1px solid #30363d; border-radius: 4px; }")
        self._console.setMinimumHeight(200)
        console_group = QGroupBox("🖥️ System Logs")
        console_group_layout = QVBoxLayout(console_group)
        console_group_layout.addWidget(self._console)
        sidebar.addWidget(console_group)

        # Wrap sidebar in a scroll area so sections keep full size
        sidebar_scroll = QScrollArea()
        sidebar_scroll.setWidgetResizable(True)
        sidebar_scroll.setWidget(sidebar_inner)
        sidebar_scroll.setFixedWidth(340)
        sidebar_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sidebar_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        upper_layout.addWidget(sidebar_scroll)

        splitter.addWidget(upper)

        # Lower section: alert log
        self._alert_log = AlertLogWidget()
        alert_group = QGroupBox("🚨 Alert History")
        alert_group_layout = QVBoxLayout(alert_group)
        alert_group_layout.addWidget(self._alert_log)
        splitter.addWidget(alert_group)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter)

        # ── Status bar ──
        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)
        self._statusbar.showMessage("Ready — configure cameras and press Start")

    # ──────────────────────────────────────────────────────────────────────────
    def _build_top_bar(self) -> QHBoxLayout:
        bar = QHBoxLayout()

        # Title
        title = QLabel("🔥 Fire & Smoke Detection System")
        title.setProperty("class", "title")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        bar.addWidget(title)

        bar.addStretch()

        # Clock
        self._clock = QLabel("00:00:00")
        self._clock.setStyleSheet(
            "font-size: 14px; color: #8b949e; font-family: 'Consolas';")
        bar.addWidget(self._clock)

        bar.addStretch()

        # System status
        self._status_dot = QLabel("⬤")
        self._status_dot.setStyleSheet("color: #8b949e; font-size: 18px;")
        bar.addWidget(self._status_dot)
        self._status_text = QLabel("Idle")
        self._status_text.setStyleSheet("color: #8b949e; font-size: 13px;")
        bar.addWidget(self._status_text)

        bar.addSpacing(20)

        # Buttons
        self._start_btn = QPushButton("▶  Start Monitoring")
        self._start_btn.setProperty("class", "success")
        self._start_btn.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self._start_btn.setFixedHeight(36)
        self._start_btn.clicked.connect(self._toggle_monitoring)
        bar.addWidget(self._start_btn)

        test_btn = QPushButton("🧪 Test Video")
        test_btn.setFixedHeight(36)
        test_btn.clicked.connect(self._add_test_video)
        bar.addWidget(test_btn)

        settings_btn = QPushButton("⚙️ Settings")
        settings_btn.setFixedHeight(36)
        settings_btn.clicked.connect(self._open_settings)
        bar.addWidget(settings_btn)

        return bar

    # ──────────────────────────────────────────────────────────────────────────


    # ══════════════════════════════════════════════════════════════════════════
    # ACTIONS
    # ══════════════════════════════════════════════════════════════════════════

    def _toggle_monitoring(self):
        if self._running:
            self._stop_monitoring()
        else:
            self._start_monitoring()

    def _start_monitoring(self):
        cameras = settings["cameras"]
        if not cameras:
            QMessageBox.warning(
                self, "No Cameras",
                "No cameras configured.\n\n"
                "Use '🧪 Test Video' to add a test video, or\n"
                "go to ⚙️ Settings → Cameras to add IP camera URLs.")
            return

        self._statusbar.showMessage("Loading models (first launch takes a moment)...")
        QApplication.processEvents()

        try:
            # Lazy-import heavy ML modules only when actually needed
            from core.stage1_classifier import Stage1Classifier
            from core.stage2_detector import Stage2Detector
            from camera.camera_manager import CameraManager  # noqa: F811

            # Load models (first time only)
            if self._classifier is None:
                self._statusbar.showMessage("Loading Stage 1 classifier...")
                QApplication.processEvents()
                self._classifier = Stage1Classifier(
                    str(settings.stage1_path),
                    num_classes=settings["num_classes"],
                )

            if self._detector is None:
                self._statusbar.showMessage("Loading Stage 2 detector...")
                QApplication.processEvents()
                self._detector = Stage2Detector(str(settings.stage2_path))

            # Lazy-create alert manager
            if self._alert_mgr is None:
                from alerts.alert_manager import AlertManager
                self._alert_mgr = AlertManager()

        except Exception as e:
            QMessageBox.critical(self, "Model Error",
                                 f"Failed to load models:\n{e}")
            logger.error(f"Model load failed: {e}")
            return

        # Create camera manager (CameraManager already imported above)
        from camera.camera_manager import CameraManager
        self._camera_mgr = CameraManager(
            classifier=self._classifier,
            detector=self._detector,
            alert_callback=self._on_alert,
        )

        # Clear old camera widgets
        for w in self._camera_widgets.values():
            self._cam_grid.removeWidget(w)
            w.deleteLater()
        self._camera_widgets.clear()

        # Add cameras
        success_count = 0
        for i, cam_cfg in enumerate(cameras):
            name = cam_cfg.get("name", f"Camera {i+1}")
            source = cam_cfg.get("url", cam_cfg.get("path", ""))
            loop = cam_cfg.get("loop", False)

            if self._camera_mgr.add_camera(name, source, loop):
                # Create widget
                widget = CameraWidget(name)
                row, col = divmod(i, 2)
                self._cam_grid.addWidget(widget, row, col)
                self._camera_widgets[name] = widget

                # Connect signals
                pipe = self._camera_mgr.pipelines[name]
                pipe.signals.frame_ready.connect(self._on_frame)
                pipe.signals.status_changed.connect(self._on_status)
                pipe.signals.detection_event.connect(self._on_detection_event)
                pipe.signals.alert_triggered.connect(self._on_immediate_alert)
                success_count += 1
            else:
                logger.error(f"Failed to open camera: {name} ({source})")

        if success_count == 0:
            QMessageBox.warning(self, "Camera Error",
                                "Failed to open any cameras.")
            return

        # Start pipelines
        self._camera_mgr.start_all()
        self._running = True
        self._start_btn.setText("⏹  Stop Monitoring")
        self._start_btn.setProperty("class", "danger")
        self._start_btn.style().unpolish(self._start_btn)
        self._start_btn.style().polish(self._start_btn)
        self._status_dot.setStyleSheet("color: #3fb950; font-size: 18px;")
        self._status_text.setText("Monitoring")
        self._status_text.setStyleSheet("color: #3fb950; font-size: 13px;")
        self._statusbar.showMessage(
            f"Monitoring {success_count} camera(s)...")
        logger.info(f"Monitoring started: {success_count} cameras")

    def _stop_monitoring(self):
        if self._camera_mgr:
            self._camera_mgr.stop_all()

        self._running = False
        
        # Visually clear cameras
        import numpy as np
        black_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        for name, widget in self._camera_widgets.items():
            widget.update_status("Stopped")
            widget.update_frame(black_frame)
            
        self._start_btn.setText("▶  Start Monitoring")
        self._start_btn.setProperty("class", "success")
        self._start_btn.style().unpolish(self._start_btn)
        self._start_btn.style().polish(self._start_btn)
        self._status_dot.setStyleSheet("color: #8b949e; font-size: 18px;")
        self._status_text.setText("Stopped")
        self._status_text.setStyleSheet("color: #8b949e; font-size: 13px;")
        self._statusbar.showMessage("Monitoring stopped")
        logger.info("Monitoring stopped")

    def _add_test_video(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Test Video", "",
            "Video Files (*.mp4 *.avi *.mkv *.mov);;All Files (*)")
        if not path:
            return

        # Add as a looping test camera
        cameras = settings["cameras"]
        name = f"Test {len(cameras) + 1}"
        cameras.append({"name": name, "url": path, "loop": True})
        settings["cameras"] = cameras
        settings.save()
        self._statusbar.showMessage(f"Added test video: {path}")
        QMessageBox.information(
            self, "Test Video Added",
            f"'{name}' added.\nPress 'Start Monitoring' to begin.")

    def _open_settings(self):
        dlg = SettingsDialog(self)
        dlg.exec()

    def _append_log(self, level: str, msg: str):
        """Append log to console with basic color formatting."""
        fmt = QTextCharFormat()
        if level == "ERROR" or level == "CRITICAL":
            fmt.setForeground(QColor("#f85149"))  # red
        elif level == "WARNING":
            fmt.setForeground(QColor("#d29922"))  # yellow
        elif level == "DEBUG":
            fmt.setForeground(QColor("#8b949e"))  # gray
        else:
            fmt.setForeground(QColor("#c9d1d9"))  # default white/gray
            
        cursor = self._console.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(msg + "\n", fmt)
        self._console.setTextCursor(cursor)
        self._console.ensureCursorVisible()

    # ══════════════════════════════════════════════════════════════════════════
    # EVENT HANDLERS
    # ══════════════════════════════════════════════════════════════════════════

    def _on_frame(self, camera_name: str, frame: np.ndarray):
        if camera_name in self._camera_widgets:
            self._camera_widgets[camera_name].update_frame(frame)

    def _on_status(self, camera_name: str, status: str):
        if camera_name in self._camera_widgets:
            self._camera_widgets[camera_name].update_status(status)
        
        # Log the stream status if it changed
        last_status_attr = f"_last_status_{camera_name}"
        last_status = getattr(self, last_status_attr, "")
        if status != last_status:
            setattr(self, last_status_attr, status)
            logger.info(f"[{camera_name}] {status}")

    def _on_detection_event(self, event: dict):
        self._alert_log.add_event(event)

    def _on_immediate_alert(self, camera_name: str, det_type: str,
                            evidence_path: str):
        """Immediate alert — plays sound as soon as Stage 2 confirms."""
        if self._alert_mgr:
            self._alert_mgr.play_sound()

    def _on_alert(self, camera_name: str, det_type: str,
                  frame: np.ndarray, evidence_path: str):
        """Called by background thread when evidence is ready — sends email."""
        if self._alert_mgr:
            self._alert_mgr.dispatch(camera_name, det_type, frame, evidence_path)

    # ══════════════════════════════════════════════════════════════════════════
    # CLOCK
    # ══════════════════════════════════════════════════════════════════════════

    def _start_clock(self):
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._update_clock)
        self._clock_timer.start(1000)
        self._update_clock()

    def _update_clock(self):
        from datetime import datetime
        self._clock.setText(datetime.now().strftime("%H:%M:%S"))

    # ══════════════════════════════════════════════════════════════════════════
    # SYSTEM TRAY
    # ══════════════════════════════════════════════════════════════════════════

    def _setup_tray_icon(self):
        from PyQt6.QtWidgets import QSystemTrayIcon, QMenu
        self.tray_icon = QSystemTrayIcon(self)
        
        # Use standard system icon for now
        icon = self.style().standardIcon(self.style().StandardPixmap.SP_ComputerIcon)
        self.tray_icon.setIcon(icon)
        
        # Build menu
        tray_menu = QMenu()
        show_action = tray_menu.addAction("Show Dashboard")
        show_action.triggered.connect(self.show)
        
        quit_action = tray_menu.addAction("Quit Application")
        quit_action.triggered.connect(self.force_quit)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()
        
        self.tray_icon.activated.connect(self._on_tray_activated)

    def _on_tray_activated(self, reason):
        from PyQt6.QtWidgets import QSystemTrayIcon
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show()

    # ══════════════════════════════════════════════════════════════════════════
    # CLEANUP
    # ══════════════════════════════════════════════════════════════════════════

    def closeEvent(self, event):
        from PyQt6.QtWidgets import QSystemTrayIcon
        if self.tray_icon.isVisible():
            self.hide()
            # Let user know it's running in background
            if not getattr(self, "_tray_msg_shown", False):
                self.tray_icon.showMessage(
                    "Running in Background",
                    "Fire & Smoke Detection is running in the system tray.",
                    QSystemTrayIcon.MessageIcon.Information,
                    2000
                )
                self._tray_msg_shown = True
            event.ignore()
        else:
            self.force_quit(event)

    def force_quit(self, event=None):
        """Force complete application shutdown."""
        self._stop_monitoring()
        if self._alert_mgr:
            self._alert_mgr.shutdown()
        settings.save()
        logger.info("Application closed")
        QApplication.quit()
