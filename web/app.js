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
  if (name === "live") loadFeed();
}
const isActive = (name) => $("view-" + name).classList.contains("active");

// ── toast ─────────────────────────────────────────────────────────────────
function toast(msg, type = "info") {
  const el = document.createElement("div");
  el.className = "toast " + type;
  el.innerHTML = `<span class="tdot"></span><span></span>`;
  el.lastChild.textContent = msg;
  $("toasts").appendChild(el);
  setTimeout(() => { el.classList.add("out"); setTimeout(() => el.remove(), 220); }, 3000);
}

// ── live video + monitoring toggle ───────────────────────────────────────────
$("liveImg").src = "/api/live";
let running = false;

$("btnToggle").addEventListener("click", () => (running ? stopMonitoring() : startMonitoring()));

async function startMonitoring() {
  const rtsp = $("sRtsp").value.trim();
  if (!rtsp) { toast("Pehle RTSP URL / video path daalo", "error"); $("sRtsp").focus(); return; }
  $("btnToggle").disabled = true;
  try {
    await api("/api/control/start", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rtsp_url: rtsp }),
    });
    $("liveImg").src = "/api/live?t=" + Date.now();
    toast("Monitoring started", "success");
    refreshStatus();
  } catch (e) { toast("Start failed: " + e.message, "error"); }
  finally { $("btnToggle").disabled = false; }
}
async function stopMonitoring() {
  $("btnToggle").disabled = true;
  try {
    await api("/api/control/stop", { method: "POST" });
    toast("Monitoring stopped", "info");
    refreshStatus();
  } catch (e) { toast("Stop failed: " + e.message, "error"); }
  finally { $("btnToggle").disabled = false; }
}

const T_PLAY = '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M8 5v14l11-7z"/></svg>';
const T_STOP = '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>';

// ── live events feed ─────────────────────────────────────────────────────────
async function loadFeed() {
  try { const d = await api("/api/events?page_size=20"); renderFeed(d.items); } catch (e) {}
}
function renderFeed(items) {
  const f = $("liveFeed");
  if (!items || !items.length) { f.innerHTML = '<div class="feed-empty">Waiting for detections…</div>'; return; }
  f.innerHTML = items.map(feedItemHtml).join("");
  f.querySelectorAll("[data-ev]").forEach((el) =>
    el.addEventListener("click", () => (el.dataset.hasclip === "1"
      ? openEvidence(el.dataset.ev, el.dataset.type)
      : openSnapshot(el.dataset.ev, el.dataset.type))));
}
function feedItemHtml(e) {
  const conf = e.confidence != null ? (e.confidence * 100).toFixed(0) + "%" : "";
  const thumb = e.has_snapshot ? `<img src="/api/events/${e.id}/snapshot" alt="snapshot"/>` : "";
  return `<div class="feed-item" data-ev="${e.id}" data-type="${e.type}" data-hasclip="${e.has_evidence ? 1 : 0}">
    ${thumb}
    <div class="fi-main"><span class="badge ${e.type}">${e.type}</span><div class="fi-time">${fmtTime(e.ts)}</div></div>
    <span class="fi-conf">${conf}</span></div>`;
}

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
    running = s.running;
    $("statusDot").className = "dot " + (running ? "on" : "off");
    $("statusLabel").textContent = running ? "Monitoring" : "Stopped";
    $("pipelineStatus").textContent = s.status_text || (running ? "Running" : "Idle");
    $("statusSdot").style.background = running
      ? (s.camera_online ? "var(--ok)" : "var(--warn)") : "var(--faint)";
    $("liveBadge").style.display = running ? "flex" : "none";
    // flipper toggle (in Settings)
    const btn = $("btnToggle");
    if (btn) {
      btn.classList.toggle("running", running);
      btn.innerHTML = (running ? T_STOP : T_PLAY) +
        `<span id="toggleLabel">${running ? "Stop monitoring" : "Start monitoring"}</span>`;
    }
    setKv("kvRunning", running, "Active", "Stopped");
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
        toast(`${last.type} detected`, "error");
        if (isActive("events")) loadEvents();
      }
      lastEventId = last.id;
    } else { lastEventId = 0; }
    if (isActive("live")) loadFeed();
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
    body.innerHTML = `<tr><td colspan="6" class="empty">No events${f.type || f.date ? " for this filter" : " yet"}.</td></tr>`;
  } else {
    body.innerHTML = data.items.map(rowHtml).join("");
    body.querySelectorAll("[data-snap]").forEach((el) =>
      el.addEventListener("click", () => openSnapshot(el.dataset.snap, el.dataset.type)));
    body.querySelectorAll("[data-ev]").forEach((el) =>
      el.addEventListener("click", () => openEvidence(el.dataset.ev, el.dataset.type)));
    body.querySelectorAll("[data-del]").forEach((el) =>
      el.addEventListener("click", () => deleteEvent(el.dataset.del)));
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
  const del = `<button class="icon-btn del" data-del="${e.id}" title="Delete event" aria-label="Delete event">${TRASH_SVG}</button>`;
  return `<tr>
    <td class="time">${fmtTime(e.ts)}</td>
    <td><span class="badge ${e.type}">${e.type}</span></td>
    <td class="conf">${conf}</td>
    <td>${thumb}</td>
    <td>${evi}</td>
    <td class="act">${del}</td></tr>`;
}
const TRASH_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2m2 0v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6M10 11v6M14 11v6"/></svg>';
async function deleteEvent(id) {
  if (!confirm(`Delete event #${id}? Snapshot + clip bhi hat jayenge.`)) return;
  try { await api(`/api/events/${id}`, { method: "DELETE" }); toast("Event deleted", "success"); loadEvents(); }
  catch (e) { toast("Delete failed: " + e.message, "error"); }
}
async function clearAllEvents() {
  if (!confirm("Saare events delete kar dein? Ye undo nahi hoga.")) return;
  try { const r = await api("/api/events", { method: "DELETE" }); toast(`${r.deleted} events cleared`, "success"); page = 1; loadEvents(); }
  catch (e) { toast("Clear failed: " + e.message, "error"); }
}
$("btnClearAll").addEventListener("click", clearAllEvents);
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
    toast("Settings saved", "success");
    if (running) toast("Naye thresholds ke liye Stop → Start karo", "info");
  } catch (e) { toast("Save failed: " + e.message, "error"); }
});

// ── boot ─────────────────────────────────────────────────────────────────────
refreshStatus();
loadSettings();
loadFeed();
setInterval(refreshStatus, 3000);
setInterval(pollNewEvents, 4000);
pollNewEvents();
