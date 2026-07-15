"""Web backend for the Fire & Smoke Detection POC.

A thin FastAPI layer over the existing detection ``core`` — runs one RTSP camera
through the two-stage pipeline, streams annotated frames to the browser (MJPEG),
and records confirmed detections as events (SQLite + snapshot + evidence MP4).
"""
