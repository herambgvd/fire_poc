"use strict";

const $ = (id) => document.getElementById(id);
const api = async (path, opts) => {
  const r = await fetch(path, opts);
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  return r.json();
};

// ── tab navigation ──────────────────────────────────────────────────────────
document.querySelectorAll(".tab").forEach((t) => {
  t.addEventListener("click", () => setView(t.dataset.view));
});
function setView(name) {
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.view === name));
  document.querySelectorAll(".view").forEach((v) => v.classList.toggle("active", v.id === `view-${name}`));
  if (name === "events") loadEvents();
  if (name === "dashboard") loadDashboard();
  if (name === "settings") loadSettings();
}

// ── live feed ────────────────────────────────────────────────────────────────
$("liveImg").src = "/api/live";

$("btnStart").addEventListener("click", async () => {
  const rtsp = $("liveRtsp").value.trim();
  try {
    await api("/api/control/start", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(rtsp ? { rtsp_url: rtsp } : {}),
    });
    // reload stream so it reconnects to fresh frames
    $("liveImg").src = "/api/live?t=" + Date.now();
    refreshStatus();
  } catch (e) { alert("Start failed: " + e.message); }
});
$("btnStop").addEventListener("click", async () => {
  try { await api("/api/control/stop", { method: "POST" }); refreshStatus(); }
  catch (e) { alert("Stop failed: " + e.message); }
});

// ── status polling ───────────────────────────────────────────────────────────
let lastEventId = null;
const setKv = (id, ok, yes, no) => {
  const el = $(id);
  el.textContent = ok ? yes : no;
  el.className = ok ? "good" : "bad";
};
async function refreshStatus() {
  try {
    const s = await api("/api/status");
    const running = s.running;
    $("statusDot").className = "dot " + (running ? "on" : "off");
    $("statusLabel").textContent = running ? "Monitoring" : "Stopped";
    $("pipelineStatus").textContent = s.status_text || (running ? "Running" : "Idle");
    $("statusSdot").style.background = running
      ? (s.camera_online ? "var(--ok)" : "var(--warn)") : "var(--faint)";
    $("liveBadge").style.display = running ? "flex" : "none";
    $("kvSource").textContent = s.source || "—";
    $("kvSource").className = s.source ? "src" : "src mut";
    setKv("kvModels", s.models_loaded, "loaded", "not loaded");
    setKv("kvCam", s.camera_online, "online", "offline");
  } catch (e) { /* ignore transient */ }
}

async function pollNewEvents() {
  try {
    const d = await api("/api/dashboard");
    const last = d.counts.last_event;
    if (last) {
      if (lastEventId !== null && last.id > lastEventId) {
        try { $("alertAudio").play().catch(() => {}); } catch (e) {}
        if (document.querySelector("#view-events").classList.contains("active")) loadEvents();
      }
      lastEventId = last.id;
    } else { lastEventId = 0; }
  } catch (e) {}
}

// ── events ───────────────────────────────────────────────────────────────────
let page = 1;
function eventFilters() {
  return { type: $("fType").value, date: $("fDate").value };
}
async function loadEvents() {
  const f = eventFilters();
  const qs = new URLSearchParams({ page, page_size: 25 });
  if (f.type) qs.set("type", f.type);
  if (f.date) qs.set("date", f.date);
  let data;
  try { data = await api("/api/events?" + qs.toString()); }
  catch (e) { return; }
  const body = $("eventsBody");
  if (!data.items.length) {
    body.innerHTML = `<tr><td colspan="5" class="empty">No events${f.type || f.date ? " for this filter" : " yet"}.</td></tr>`;
  } else {
    body.innerHTML = data.items.map(rowHtml).join("");
    body.querySelectorAll("[data-snap]").forEach((el) =>
      el.addEventListener("click", () => openSnapshot(el.dataset.snap, el.dataset.type)));
    body.querySelectorAll("[data-ev]").forEach((el) =>
      el.addEventListener("click", () => openEvidence(el.dataset.ev, el.dataset.type)));
  }
  const pages = Math.max(1, Math.ceil(data.total / data.page_size));
  $("pgInfo").textContent = `Page ${data.page} / ${pages} · ${data.total} events`;
  $("pgPrev").disabled = data.page <= 1;
  $("pgNext").disabled = data.page >= pages;
}
function fmtTime(iso) {
  try { return new Date(iso).toLocaleString(); } catch (e) { return iso; }
}
const PLAY_SVG = '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M8 5v14l11-7z"/></svg>';
function rowHtml(e) {
  const conf = e.confidence != null ? (e.confidence * 100).toFixed(0) + "%" : "—";
  const thumb = e.has_snapshot
    ? `<img class="thumb" src="/api/events/${e.id}/snapshot" data-snap="${e.id}" data-type="${e.type}" alt="detection snapshot" title="Click to enlarge"/>`
    : '<span class="mut">—</span>';
  const evi = e.has_evidence
    ? `<button class="link-btn" data-ev="${e.id}" data-type="${e.type}">${PLAY_SVG}View clip</button>`
    : '<span class="mut">—</span>';
  return `<tr>
    <td class="time">${fmtTime(e.ts)}</td>
    <td><span class="badge ${e.type}">${e.type}</span></td>
    <td class="conf">${conf}</td>
    <td>${thumb}</td>
    <td>${evi}</td></tr>`;
}
$("btnFilter").addEventListener("click", () => { page = 1; loadEvents(); });
$("btnClear").addEventListener("click", () => { $("fType").value = ""; $("fDate").value = ""; page = 1; loadEvents(); });
$("pgPrev").addEventListener("click", () => { if (page > 1) { page--; loadEvents(); } });
$("pgNext").addEventListener("click", () => { page++; loadEvents(); });

// ── evidence modal ───────────────────────────────────────────────────────────
function openEvidence(id, type) {
  $("modalTitle").textContent = `Evidence clip — ${type} (event #${id})`;
  const img = $("modalImg"); img.style.display = "none"; img.src = "";
  const v = $("modalVideo"); v.style.display = "block"; v.src = `/api/events/${id}/evidence`;
  $("modal").classList.add("open");
}
function openSnapshot(id, type) {
  $("modalTitle").textContent = `Snapshot — ${type} (event #${id})`;
  const v = $("modalVideo"); v.pause(); v.src = ""; v.style.display = "none";
  const img = $("modalImg"); img.src = `/api/events/${id}/snapshot`; img.style.display = "block";
  $("modal").classList.add("open");
}
$("modalClose").addEventListener("click", closeModal);
$("modal").addEventListener("click", (e) => { if (e.target.id === "modal") closeModal(); });
function closeModal() {
  $("modal").classList.remove("open");
  const v = $("modalVideo"); v.pause(); v.src = "";
  $("modalImg").src = "";
}

// ── dashboard ────────────────────────────────────────────────────────────────
async function loadDashboard() {
  let d;
  try { d = await api("/api/dashboard"); } catch (e) { return; }
  const c = d.counts, s = d.status;
  $("dToday").textContent = c.today;
  $("dTotal").textContent = c.total;
  $("dFire").textContent = c.fire;
  $("dSmoke").textContent = c.smoke;
  setKv("dRunning", s.running, "Yes", "No");
  setKv("dCam", s.camera_online, "Yes", "No");
  setKv("dModels", s.models_loaded, "Yes", "No");
  $("dPipe").textContent = s.status_text || "—";
  $("dPipe").className = "";
  $("dLast").innerHTML = c.last_event
    ? `<span class="badge ${c.last_event.type}">${c.last_event.type}</span> <span class="mono">${fmtTime(c.last_event.ts)}</span>`
    : "No events yet.";
}

// ── settings ─────────────────────────────────────────────────────────────────
const SMAP = {
  rtsp_url: "sRtsp", classifier_threshold: "sClsThr", consecutive_frames_required: "sConsec",
  yolo_confidence: "sYoloConf", yolo_iou: "sYoloIou", alert_cooldown_seconds: "sCooldown",
  post_detection_seconds: "sPost", buffer_seconds: "sBuffer",
};
async function loadSettings() {
  let s;
  try { s = await api("/api/settings"); } catch (e) { return; }
  for (const [k, id] of Object.entries(SMAP)) if (s[k] != null) $(id).value = s[k];
  if (s.rtsp_url && !$("liveRtsp").value) $("liveRtsp").value = s.rtsp_url;
}
$("btnSaveSettings").addEventListener("click", async () => {
  const body = {};
  for (const [k, id] of Object.entries(SMAP)) {
    const v = $(id).value;
    if (v !== "") body[k] = v;
  }
  try {
    await api("/api/settings", {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    $("saveMsg").textContent = "Saved ✓"; $("saveMsg").className = "save-msg";
    setTimeout(() => ($("saveMsg").textContent = ""), 2500);
    if (body.rtsp_url) $("liveRtsp").value = body.rtsp_url;
  } catch (e) { $("saveMsg").textContent = "Error: " + e.message; $("saveMsg").className = "save-msg err"; }
});

// ── boot ─────────────────────────────────────────────────────────────────────
refreshStatus();
loadSettings();
setInterval(refreshStatus, 3000);
setInterval(pollNewEvents, 4000);
pollNewEvents();
