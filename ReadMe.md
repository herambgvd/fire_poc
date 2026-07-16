# Fire & Smoke Detection — Web POC

Real-time fire & smoke detection for a single RTSP/CCTV camera, served as a
**web app**. A lightweight two-stage deep-learning pipeline
(**MobileNetV3-Small** screening → **YOLOv11n** confirmation) runs on the server;
the browser shows the **annotated live feed** and a searchable **event history**
with snapshots and evidence clips.

This is a **POC** (single camera, no login). The production system,
`vizor_ai_fire`, will run on the vizor platform (auth, multi-camera, storage,
notifications already provided there).

> A legacy PyQt6 **desktop** build also still works (`python main.py`) — it shares
> the same detection `core/`. This README covers the **web** build.

---

## Features

| Page | What it does |
|------|--------------|
| **Live** | RTSP feed streamed to the browser as annotated frames (server draws Stage-2 boxes) via MJPEG. Start/stop monitoring from the UI. |
| **Events** | Every confirmed fire/smoke detection stored (SQLite) with a snapshot + evidence MP4. Filter by type/date, export CSV, play the clip. |
| **Dashboard** | Today/total counts, Fire/Smoke split, system status, last event. |
| **Settings** | RTSP URL + detection thresholds, persisted to `settings.json`. |

## Detection pipeline
```
RTSP frame
   ↓  Stage 1 — MobileNetV3-Small (cheap, every frame) — screening
   ↓  (N consecutive hits escalate)
   ↓  Stage 2 — YOLOv11n — confirm + draw bounding boxes
   ↓  Confirmed → alert + snapshot + evidence MP4 + event row
```
Stage 1 is a cheap high-recall screen; Stage 2 confirms and localizes. Stage 2
only runs after Stage 1 escalates, so the system stays light on CPU.

## Project layout
```
core/            two-stage detection (framework-agnostic; callback interface)
server/          FastAPI backend
  main.py          routes + MJPEG live stream + serves the SPA
  runner.py        loads models, runs one camera, holds latest annotated frame
  store.py         SQLite events + snapshot files
web/             static SPA (dark, vizor-style) — no build step
data/            (gitignored) fire_poc.db, snapshots/
evidence/        (gitignored) evidence .mp4 clips
models:          mobilenetv3_small_stage1_with_normal.pth, yolon11_stage2_with_normal.pt
```

---

## Run with Docker (recommended)

Prereqs: Docker + Docker Compose.

```bash
docker compose up -d --build          # CPU
```

**GPU box** (NVIDIA driver + nvidia-container-toolkit, e.g. the wonin server):
```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build
```
This builds the CUDA torch image and gives the container a GPU; detection runs on
CUDA automatically (check `docker compose logs -f` for `models loaded (device=cuda)`).

Open **http://localhost:8080** → **Settings** (or the Live panel) → paste the RTSP
URL → **Start monitoring**.

- Data (events DB, snapshots, evidence clips) persists in named volumes
  (`fire_data`, `fire_evidence`) across restarts.
- Change the host port by editing `docker-compose.yml` (`"8080:8080"`).
- Logs: `docker compose logs -f`   ·   Stop: `docker compose down`

A local video file also works for demos — copy it into the project, then use its
in-container path (e.g. `/app/demo.mp4`) as the "RTSP URL" (it loops).

## Run without Docker

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-web.txt
python run_web.py            # or: python -m server.main
```
Open http://localhost:8080. `PORT=9000 python run_web.py` to change the port.

---

## Notes
- CPU-only by design.
- After changing detection settings, **Stop → Start** monitoring to apply them.
- Models are bundled in the repo; no external download needed.

## Credits
Original two-stage detection system by Arfa Riaz & Waqas Ul Hasan
(https://github.com/waqasuh/DIP-Project). Web POC re-platforming on top of that core.
