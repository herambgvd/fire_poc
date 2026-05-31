"""
Fire & Smoke Detection System — Application Entry Point.

Usage:
    python main.py                           # Launch GUI
    python main.py --test path/to/video.mp4  # Launch with test video pre-loaded
"""

import sys
import os
import argparse
import logging

# Ensure the Application directory is on sys.path for local imports
_APP_DIR = os.path.dirname(os.path.abspath(__file__))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

from config import settings, LOGS_DIR, EVIDENCE_DIR
from logging_config import setup_logging


def main():
    """
    Main function to initialize and launch the application.
    This parses arguments, sets up logging, initializes directories,
    handles test videos, and starts the PyQt6 GUI.
    """
    # ── Parse CLI args ──
    # ArgumentParser allows us to pass arguments via command line (e.g., --test)
    parser = argparse.ArgumentParser(
        description="Fire & Smoke Detection System")
    parser.add_argument("--test", type=str, default=None,
                        help="Path to a test video file (adds it as a looping camera)")
    args = parser.parse_args()

    # ── Init logging ──
    setup_logging(logging.INFO)
    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("  Fire & Smoke Detection System Starting")
    logger.info("=" * 60)

    # ── Create dirs ──
    # Ensure that the directories for logs and evidence exist before the app starts
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    # ── Add test video if specified ──
    # If a user provides a video via the --test argument, it is automatically
    # appended to the camera settings list as a looping camera feed.
    if args.test:
        cameras = settings["cameras"]
        # Don't duplicate
        if not any(c.get("url") == args.test for c in cameras):
            cameras.append({
                "name": f"Test Video",
                "url": args.test,
                "loop": True,
            })
            settings["cameras"] = cameras
            settings.save()
            logger.info(f"Test video added: {args.test}")

    # ── Launch GUI ──
    # We import PyQt6 components locally here to avoid importing them 
    # if we only needed to run a CLI script (although this app is GUI-first).
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt

    # High-DPI support (must be set before QApplication is created)
    # This ensures that the application scales correctly on high-resolution screens.
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    # Initialize the main QApplication loop
    app = QApplication(sys.argv)
    app.setApplicationName("Fire & Smoke Detection System")
    app.setStyle("Fusion")  # Consistent look across platforms

    from gui.dashboard import Dashboard
    window = Dashboard()
    window.show()

    logger.info("GUI launched")
    
    # app.exec() starts the main Qt event loop. The program will block here
    # until the main window is closed by the user.
    sys.exit(app.exec())


# Standard Python boilerplate to ensure main() is only called if this script
# is executed directly (not imported as a module).
if __name__ == "__main__":
    main()
