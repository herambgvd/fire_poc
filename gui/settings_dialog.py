"""
Settings dialog — live tuning of detection thresholds, camera config, email setup.
Changes take effect immediately (no restart needed).
"""

from pathlib import Path
from PyQt6.QtCore import Qt, QEvent
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLabel, QDoubleSpinBox, QSpinBox, QLineEdit, QPushButton,
    QCheckBox, QGroupBox, QFormLayout, QListWidget, QFileDialog,
    QSlider, QFrame, QListWidgetItem, QMessageBox, QScrollArea,
)

from config import settings


class SettingsDialog(QDialog):
    """Tabbed settings dialog with live threshold adjustment."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙️ Settings — Fire & Smoke Detection System")
        self.setMinimumSize(600, 520)

        layout = QVBoxLayout(self)

        tabs = QTabWidget()
        tabs.addTab(self._build_detection_tab(), "🔍 Detection")
        tabs.addTab(self._build_email_tab(), "📧 Email")
        tabs.addTab(self._build_cameras_tab(), "📷 Cameras")
        layout.addWidget(tabs)

        # Explanation Panel
        self.explanation_label = QLabel("ℹ️ Click on any setting input field to see its details here.")
        self.explanation_label.setWordWrap(True)
        self.explanation_label.setStyleSheet(
            "color: #c9d1d9; font-size: 12px; padding: 10px; "
            "border: 1px solid #30363d; border-radius: 4px; background: #0d1117;"
        )
        self.explanation_label.setMinimumHeight(70)
        layout.addWidget(self.explanation_label)

        # Save / Close
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        save_btn = QPushButton("Save Settings")
        save_btn.setProperty("class", "primary")
        save_btn.clicked.connect(self._save)
        btn_layout.addWidget(save_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        self._setup_explanations()

    def eventFilter(self, obj, event):
        """Intercept focus events to update the explanation panel."""
        if event.type() == QEvent.Type.FocusIn:
            if obj in self._explanations:
                self.explanation_label.setText(f"ℹ️ <b>{self._explanations[obj]['title']}</b><br>{self._explanations[obj]['desc']}")
        return super().eventFilter(obj, event)

    def _setup_explanations(self):
        """Map input fields to their explanation text and install event filters."""
        self._explanations = {
            self.clf_threshold: {
                "title": "Classification Threshold", 
                "desc": "The minimum probability required for the Stage 1 model to consider a frame as having fire or smoke. A lower value makes the system more sensitive but increases false alarms."
            },
            self.consec_frames: {
                "title": "Consecutive Frames to Escalate",
                "desc": "The number of consecutive frames Stage 1 must detect fire/smoke before triggering the heavier Stage 2 model. Higher values reduce false alarms from brief glitches."
            },
            self.yolo_conf: {
                "title": "YOLO Confidence Threshold",
                "desc": "The minimum confidence score for Stage 2 to confirm an object is fire or smoke. Lowering this will detect more fires but may misclassify objects."
            },
            self.yolo_iou: {
                "title": "YOLO IOU Threshold",
                "desc": "Intersection Over Union. Controls how overlapping bounding boxes are merged. A lower value merges boxes more aggressively."
            },
            self.cooldown: {
                "title": "Alert Cooldown",
                "desc": "Minimum time (in seconds) to wait before triggering another alert after an escalation. Prevents spamming alerts for the same continuous event."
            },
            self.buffer_secs: {
                "title": "Pre-detection Buffer",
                "desc": "The number of seconds of video to keep in memory at all times. This gets attached to the beginning of the evidence video to show what happened before the fire started."
            },
            self.max_await: {
                "title": "Max Await Stage 2",
                "desc": "How long Stage 2 will actively scan live frames waiting for a confirmation before timing out and returning to normal mode."
            },
            self.post_detect: {
                "title": "Post-Detection Proof",
                "desc": "How many seconds of video to record *after* Stage 2 confirms a fire, providing proof of the event."
            },
            self.smtp_server: {
                "title": "SMTP Server",
                "desc": "The outgoing mail server used to send email alerts (e.g., smtp.gmail.com)."
            },
            self.smtp_port: {
                "title": "SMTP Port",
                "desc": "The port for the SMTP server (usually 465 for SSL or 587 for TLS)."
            },
            self.smtp_email: {
                "title": "Sender Email",
                "desc": "The email address that will send the alert emails."
            },
            self.smtp_password: {
                "title": "Password",
                "desc": "The password or app-specific password for the sender email account."
            },
            self.new_email: {
                "title": "Add Recipient",
                "desc": "Type an email address here and click 'Add' to include them in the alert notification list."
            },
            self.cam_name: {
                "title": "Camera Name",
                "desc": "A friendly display name for the camera feed."
            },
            self.cam_url: {
                "title": "Camera URL / Path",
                "desc": "The RTSP stream URL for an IP camera, or the local path to a video file for testing."
            },
        }

        # Install the event filter on all tracked input fields
        for widget in self._explanations.keys():
            widget.installEventFilter(self)

    # ── Detection Tab ─────────────────────────────────────────────────────────
    def _build_detection_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        w = QWidget()
        layout = QVBoxLayout(w)

        # Stage 1 settings
        s1_group = QGroupBox("Stage 1 — Classifier (MobileNetV3-Small)")
        s1_form = QFormLayout(s1_group)

        self.clf_threshold = QDoubleSpinBox()
        self.clf_threshold.setRange(0.01, 0.99)
        self.clf_threshold.setSingleStep(0.05)
        self.clf_threshold.setDecimals(2)
        self.clf_threshold.setValue(settings["classifier_threshold"])
        s1_form.addRow("Classification Threshold:", self.clf_threshold)

        self.consec_frames = QSpinBox()
        self.consec_frames.setRange(1, 20)
        self.consec_frames.setValue(settings["consecutive_frames_required"])
        s1_form.addRow("Consecutive Frames to Escalate:", self.consec_frames)

        layout.addWidget(s1_group)

        # Stage 2 settings
        s2_group = QGroupBox("Stage 2 — Detector (YOLO11n)")
        s2_form = QFormLayout(s2_group)

        self.yolo_conf = QDoubleSpinBox()
        self.yolo_conf.setRange(0.01, 0.99)
        self.yolo_conf.setSingleStep(0.05)
        self.yolo_conf.setDecimals(2)
        self.yolo_conf.setValue(settings["yolo_confidence"])
        s2_form.addRow("YOLO Confidence Threshold:", self.yolo_conf)

        self.yolo_iou = QDoubleSpinBox()
        self.yolo_iou.setRange(0.01, 0.99)
        self.yolo_iou.setSingleStep(0.05)
        self.yolo_iou.setDecimals(2)
        self.yolo_iou.setValue(settings["yolo_iou"])
        s2_form.addRow("YOLO IOU Threshold:", self.yolo_iou)

        layout.addWidget(s2_group)

        # Alert settings
        alert_group = QGroupBox("Alert Settings")
        alert_form = QFormLayout(alert_group)

        self.cooldown = QSpinBox()
        self.cooldown.setRange(5, 600)
        self.cooldown.setSuffix(" seconds")
        self.cooldown.setValue(settings["alert_cooldown_seconds"])
        alert_form.addRow("Alert Cooldown:", self.cooldown)

        sound_layout = QHBoxLayout()
        self.sound_enabled = QCheckBox("Enable Sound Alerts")
        self.sound_enabled.setChecked(settings["sound_enabled"])
        sound_info = QLabel("ℹ️")
        sound_info.setToolTip("Plays an alarm sound immediately when Stage 2 confirms a fire or smoke event.")
        sound_layout.addWidget(self.sound_enabled)
        sound_layout.addWidget(sound_info)
        sound_layout.addStretch()
        alert_form.addRow(sound_layout)

        self.buffer_secs = QSpinBox()
        self.buffer_secs.setRange(5, 60)
        self.buffer_secs.setSuffix(" seconds")
        self.buffer_secs.setValue(settings["buffer_seconds"])
        alert_form.addRow("Pre-detection Buffer:", self.buffer_secs)

        self.max_await = QSpinBox()
        self.max_await.setRange(1, 60)
        self.max_await.setSuffix(" seconds")
        self.max_await.setValue(settings["max_await_seconds"])
        alert_form.addRow("Max Await Stage 2:", self.max_await)

        self.post_detect = QSpinBox()
        self.post_detect.setRange(1, 60)
        self.post_detect.setSuffix(" seconds")
        self.post_detect.setValue(settings["post_detection_seconds"])
        alert_form.addRow("Post-Detection Proof:", self.post_detect)

        layout.addWidget(alert_group)
        layout.addStretch()
        
        scroll.setWidget(w)
        return scroll

    # ── Email Tab ─────────────────────────────────────────────────────────────
    def _build_email_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        w = QWidget()
        layout = QVBoxLayout(w)

        smtp_group = QGroupBox("SMTP Configuration")
        smtp_form = QFormLayout(smtp_group)

        self.smtp_server = QLineEdit(settings["smtp_server"])
        smtp_form.addRow("SMTP Server:", self.smtp_server)

        self.smtp_port = QSpinBox()
        self.smtp_port.setRange(1, 65535)
        self.smtp_port.setValue(settings["smtp_port"])
        smtp_form.addRow("SMTP Port:", self.smtp_port)

        self.smtp_email = QLineEdit(settings["smtp_email"])
        self.smtp_email.setPlaceholderText("your_email@gmail.com")
        smtp_form.addRow("Sender Email:", self.smtp_email)

        self.smtp_password = QLineEdit(settings["smtp_password"])
        self.smtp_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.smtp_password.setPlaceholderText("App password")
        smtp_form.addRow("Password:", self.smtp_password)

        layout.addWidget(smtp_group)

        # Recipients
        recip_group = QGroupBox("Alert Recipients")
        recip_layout = QVBoxLayout(recip_group)

        self.recip_list = QListWidget()
        self.recip_list.setToolTip("List of emails that will receive alert notifications with evidence attached.")
        for email in settings["email_recipients"]:
            self.recip_list.addItem(email)
        recip_layout.addWidget(self.recip_list)

        add_row = QHBoxLayout()
        self.new_email = QLineEdit()
        self.new_email.setPlaceholderText("recipient@example.com")
        add_row.addWidget(self.new_email)

        add_btn = QPushButton("Add")
        add_btn.setProperty("class", "success")
        add_btn.clicked.connect(self._add_recipient)
        add_row.addWidget(add_btn)

        rm_btn = QPushButton("Remove Selected")
        rm_btn.setProperty("class", "danger")
        rm_btn.clicked.connect(self._remove_recipient)
        add_row.addWidget(rm_btn)

        recip_layout.addLayout(add_row)
        layout.addWidget(recip_group)
        layout.addStretch()
        
        scroll.setWidget(w)
        return scroll

    # ── Cameras Tab ───────────────────────────────────────────────────────────
    def _build_cameras_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        w = QWidget()
        layout = QVBoxLayout(w)

        info = QLabel(
            "Add IP camera URLs (rtsp:// or http://) or local video files for test mode.\n"
            "Changes take effect on next Start."
        )
        info.setStyleSheet("color: #8b949e; font-size: 11px; padding: 4px;")
        info.setWordWrap(True)
        layout.addWidget(info)

        self.cam_list = QListWidget()
        self.cam_list.setToolTip("List of configured cameras. Select a camera to remove it.")
        for cam in settings["cameras"]:
            display = f"{cam.get('name', 'Cam')} — {cam.get('url', cam.get('path', ''))}"
            self.cam_list.addItem(display)
        layout.addWidget(self.cam_list)

        # Add camera row
        form = QFormLayout()
        self.cam_name = QLineEdit()
        self.cam_name.setPlaceholderText("Camera 1")
        form.addRow("Name:", self.cam_name)

        url_row = QHBoxLayout()
        self.cam_url = QLineEdit()
        self.cam_url.setPlaceholderText("rtsp://... or video file path")
        url_row.addWidget(self.cam_url)

        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._browse_video)
        url_row.addWidget(browse_btn)
        form.addRow("URL / Path:", url_row)

        loop_layout = QHBoxLayout()
        self.cam_loop = QCheckBox("Loop video (test mode)")
        loop_info = QLabel("ℹ️")
        loop_info.setToolTip("If checked, the local video file will automatically restart when it reaches the end. Useful for testing.")
        loop_layout.addWidget(self.cam_loop)
        loop_layout.addWidget(loop_info)
        loop_layout.addStretch()
        form.addRow(loop_layout)
        layout.addLayout(form)

        btn_row = QHBoxLayout()
        add_cam = QPushButton("Add Camera")
        add_cam.setProperty("class", "success")
        add_cam.clicked.connect(self._add_camera)
        btn_row.addWidget(add_cam)

        rm_cam = QPushButton("Remove Selected")
        rm_cam.setProperty("class", "danger")
        rm_cam.clicked.connect(self._remove_camera)
        btn_row.addWidget(rm_cam)
        layout.addLayout(btn_row)

        layout.addStretch()
        
        scroll.setWidget(w)
        return scroll

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _add_recipient(self):
        email = self.new_email.text().strip()
        if email and "@" in email:
            self.recip_list.addItem(email)
            self.new_email.clear()

    def _remove_recipient(self):
        for item in self.recip_list.selectedItems():
            self.recip_list.takeItem(self.recip_list.row(item))

    def _browse_video(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Video File", "",
            "Video Files (*.mp4 *.avi *.mkv *.mov);;All Files (*)")
        if path:
            self.cam_url.setText(path)

    def _add_camera(self):
        name = self.cam_name.text().strip() or f"Camera {self.cam_list.count() + 1}"
        url = self.cam_url.text().strip()
        if not url:
            return
        cam = {"name": name, "url": url, "loop": self.cam_loop.isChecked()}
        cameras = settings["cameras"]
        cameras.append(cam)
        settings["cameras"] = cameras
        self.cam_list.addItem(f"{name} — {url}")
        self.cam_name.clear()
        self.cam_url.clear()

    def _remove_camera(self):
        for item in self.cam_list.selectedItems():
            idx = self.cam_list.row(item)
            self.cam_list.takeItem(idx)
            cameras = settings["cameras"]
            if idx < len(cameras):
                cameras.pop(idx)
                settings["cameras"] = cameras

    def _save(self):
        """Save all settings from the dialog widgets back to config."""
        settings["classifier_threshold"] = self.clf_threshold.value()
        settings["consecutive_frames_required"] = self.consec_frames.value()
        settings["yolo_confidence"] = self.yolo_conf.value()
        settings["yolo_iou"] = self.yolo_iou.value()
        settings["alert_cooldown_seconds"] = self.cooldown.value()
        settings["sound_enabled"] = self.sound_enabled.isChecked()
        settings["buffer_seconds"] = self.buffer_secs.value()
        settings["max_await_seconds"] = self.max_await.value()
        settings["post_detection_seconds"] = self.post_detect.value()

        settings["smtp_server"] = self.smtp_server.text().strip()
        settings["smtp_port"] = self.smtp_port.value()
        settings["smtp_email"] = self.smtp_email.text().strip()
        settings["smtp_password"] = self.smtp_password.text()

        recipients = []
        for i in range(self.recip_list.count()):
            recipients.append(self.recip_list.item(i).text())
        settings["email_recipients"] = recipients

        settings.save()
        QMessageBox.information(self, "Settings",
                                "Settings saved successfully!")
