"""FastAPI application for the Fire & Smoke Detection web POC.

Run:  python -m server.main       (from the fire_poc/ directory)
Then open http://localhost:8080

Serves the static SPA at ``/`` and a small JSON/stream API under ``/api``.
"""

from __future__ import annotations

import logging
import os
import sys
import time

# Make the project root importable (config, core, camera live at the top level).
_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

import cv2
import numpy as np
from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from config import ALERT_SOUND_FILE, settings
from logging_config import setup_logging
from server import store
from server.runner import runner

setup_logging(logging.INFO)
log = logging.getLogger("fire.web")

# Ensure the DB/dirs exist at import time (idempotent) — robust even if the
# ASGI startup lifecycle doesn't run (e.g. TestClient without a context manager).
store.init_db()

app = FastAPI(title="Fire & Smoke Detection — POC")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

# Settings the UI is allowed to read/write (everything else stays internal).
_EDITABLE = [
    "rtsp_url", "classifier_threshold", "consecutive_frames_required",
    "yolo_confidence", "yolo_iou", "alert_cooldown_seconds",
    "post_detection_seconds", "buffer_seconds",
]
_FLOAT_KEYS = {"classifier_threshold", "yolo_confidence", "yolo_iou"}
_INT_KEYS = {"consecutive_frames_required", "alert_cooldown_seconds",
             "post_detection_seconds", "buffer_seconds"}


@app.on_event("startup")
def _startup() -> None:
    store.init_db()
    log.info("Fire POC web server ready")


# ── placeholder frame (shown when no live frame is available yet) ───────────
def _placeholder_jpeg() -> bytes:
    img = np.zeros((360, 640, 3), dtype=np.uint8)
    img[:] = (28, 28, 32)
    cv2.putText(img, "No live signal", (180, 190),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (120, 120, 130), 2)
    ok, buf = cv2.imencode(".jpg", img)
    return buf.tobytes()


_PLACEHOLDER = _placeholder_jpeg()


# ── live MJPEG stream ───────────────────────────────────────────────────────
def _mjpeg_generator():
    boundary = b"--frame"
    while True:
        jpeg = runner.latest_jpeg() or _PLACEHOLDER
        yield (boundary + b"\r\nContent-Type: image/jpeg\r\n"
               + f"Content-Length: {len(jpeg)}\r\n\r\n".encode() + jpeg + b"\r\n")
        time.sleep(1 / 15)


@app.get("/api/live")
def live():
    return StreamingResponse(
        _mjpeg_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


# ── control + status ────────────────────────────────────────────────────────
@app.get("/api/status")
def status():
    return runner.status()


@app.post("/api/control/start")
def control_start(body: dict = Body(default={})):
    url = (body or {}).get("rtsp_url")
    if url:
        settings["rtsp_url"] = url
        settings.save()
    try:
        runner.start(url)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return runner.status()


@app.post("/api/control/stop")
def control_stop():
    runner.stop()
    return runner.status()


# ── events ──────────────────────────────────────────────────────────────────
@app.get("/api/events")
def events(type: str | None = Query(default=None),
           date: str | None = Query(default=None),
           page: int = Query(default=1, ge=1),
           page_size: int = Query(default=25, ge=1, le=200)):
    return store.list_events(type=type, date=date, page=page, page_size=page_size)


@app.get("/api/events/export.csv")
def events_csv():
    import csv
    import io

    rows = store.all_events()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "timestamp_utc", "camera", "type", "confidence",
                "stage1", "stage2", "snapshot", "evidence"])
    for e in rows:
        w.writerow([e["id"], e["ts"], e["camera"], e["type"], e.get("confidence"),
                    e.get("stage1"), e.get("stage2"), e.get("snapshot"),
                    e.get("evidence")])
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=fire_events.csv"},
    )


def _remove_event_files(e: dict) -> None:
    if e.get("snapshot"):
        try: (store.SNAPSHOT_DIR / e["snapshot"]).unlink(missing_ok=True)
        except OSError: pass
    if e.get("evidence") and os.path.isfile(e["evidence"]):
        try: os.remove(e["evidence"])
        except OSError: pass


@app.delete("/api/events")
def clear_events():
    rows = store.clear_events()
    for e in rows:
        _remove_event_files(e)
    return {"deleted": len(rows)}


@app.delete("/api/events/{event_id}")
def delete_event(event_id: int):
    e = store.delete_event(event_id)
    if not e:
        raise HTTPException(status_code=404, detail="event not found")
    _remove_event_files(e)
    return {"deleted": event_id}


@app.get("/api/events/{event_id}")
def event_detail(event_id: int):
    e = store.get_event(event_id)
    if not e:
        raise HTTPException(status_code=404, detail="event not found")
    return e


@app.get("/api/events/{event_id}/snapshot")
def event_snapshot(event_id: int):
    e = store.get_event(event_id)
    if not e or not e.get("snapshot"):
        raise HTTPException(status_code=404, detail="no snapshot")
    path = store.SNAPSHOT_DIR / e["snapshot"]
    if not path.is_file():
        raise HTTPException(status_code=404, detail="snapshot file missing")
    return FileResponse(str(path), media_type="image/jpeg")


@app.get("/api/events/{event_id}/evidence")
def event_evidence(event_id: int):
    e = store.get_event(event_id)
    if not e or not e.get("evidence"):
        raise HTTPException(status_code=404, detail="no evidence")
    path = e["evidence"]
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="evidence file missing")
    return FileResponse(path, media_type="video/mp4")


# ── dashboard ────────────────────────────────────────────────────────────────
@app.get("/api/dashboard")
def dashboard():
    return {"counts": store.counts_today(), "status": runner.status()}


# ── settings ─────────────────────────────────────────────────────────────────
@app.get("/api/settings")
def get_settings():
    return {k: settings.get(k) for k in _EDITABLE}


@app.get("/api/roi")
def get_roi():
    return {"roi": settings.get("roi")}


@app.put("/api/roi")
def put_roi(body: dict = Body(...)):
    roi = (body or {}).get("roi")
    if roi is None:
        settings["roi"] = None
    else:
        try:
            x1, y1, x2, y2 = (float(v) for v in roi)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="roi must be [x1,y1,x2,y2] normalized 0-1, or null")
        clamp = lambda v: max(0.0, min(1.0, v))
        x1, x2 = sorted((clamp(x1), clamp(x2)))
        y1, y2 = sorted((clamp(y1), clamp(y2)))
        if (x2 - x1) < 0.03 or (y2 - y1) < 0.03:
            raise HTTPException(status_code=400, detail="ROI too small — draw a bigger region")
        settings["roi"] = [x1, y1, x2, y2]
    settings.save()
    return {"roi": settings.get("roi")}


@app.put("/api/settings")
def put_settings(body: dict = Body(...)):
    changed = {}
    for k, v in (body or {}).items():
        if k not in _EDITABLE:
            continue
        try:
            if k in _FLOAT_KEYS:
                v = float(v)
            elif k in _INT_KEYS:
                v = int(v)
            else:
                v = str(v)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail=f"bad value for {k}")
        settings[k] = v
        changed[k] = v
    settings.save()
    return {"updated": changed, "settings": {k: settings.get(k) for k in _EDITABLE}}


@app.get("/api/alert-sound")
def alert_sound():
    if not os.path.isfile(str(ALERT_SOUND_FILE)):
        raise HTTPException(status_code=404, detail="no alert sound")
    return FileResponse(str(ALERT_SOUND_FILE), media_type="audio/mpeg")


# ── static SPA (must be mounted LAST so /api/* wins) ────────────────────────
_WEB_DIR = os.path.join(_APP_DIR, "web")
app.mount("/", StaticFiles(directory=_WEB_DIR, html=True), name="web")


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
