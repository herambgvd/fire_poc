# Fire & Smoke Detection — Web POC

A web-based version of the fire/smoke detector. The existing two-stage detection
`core` (MobileNetV3 screening → YOLOv11n confirmation) is reused unchanged; only
the desktop PyQt GUI is replaced by a small **FastAPI + static SPA** front end.

POC scope: **one RTSP camera**, no login (the production `vizor_ai_fire` will run
on the vizor platform which already provides auth/multi-camera/etc.).

## What it does
- **Live** — RTSP feed streamed to the browser as annotated frames (server draws
  the Stage-2 bounding boxes), via MJPEG. Start/stop monitoring from the UI.
- **Events** — every confirmed fire/smoke detection is stored (SQLite) with a
  snapshot + evidence MP4. Filter by type/date, export CSV, play the evidence clip.
- **Dashboard** — today/total counts, Fire/Smoke split, system status, last event.
- **Settings** — RTSP URL + detection thresholds (persisted to `settings.json`).

## Architecture
```
core/            # existing detection pipeline (now PyQt-free: callback interface)
server/          # FastAPI backend
  main.py        #   routes + MJPEG live stream + serves the SPA
  runner.py      #   loads models, runs one camera, holds latest annotated frame
  store.py       #   SQLite events + snapshot files
web/             # static SPA (dark, vizor-style) — no build step
data/            # (gitignored) fire_poc.db, snapshots/, and evidence/ mp4s
models: mobilenetv3_small_stage1_with_normal.pth, yolon11_stage2_with_normal.pt
```

## Run
```bash
python -m venv .venv && source .venv/bin/activate      # (Windows: .venv\Scripts\activate)
pip install -r requirements-web.txt
python run_web.py            # or: python -m server.main
```
Open **http://localhost:8080**, go to **Settings** (or the Live panel), paste the
RTSP URL, then **Start monitoring**. A local video file path also works (it loops)
for demos.

`PORT=9000 python run_web.py` to change the port.

## Notes
- CPU-only by design (matches the original POC).
- The desktop app (`python main.py`, PyQt6) still works — the core is shared.
- After changing detection settings, Stop → Start monitoring to apply them.
