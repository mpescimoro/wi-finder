"""Web UI for WiFinder."""

import threading
import time
from datetime import datetime
from pathlib import Path

from flask import Flask, render_template_string, jsonify, request, send_from_directory

from .config import Config
from .database import Database
from .watcher import Watcher

# Static files directory
STATIC_DIR = Path(__file__).parent / "static"

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>WiFinder</title>
<link rel="icon" type="image/png" href="/static/favicon.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root {
  --bg: #0e0e11;
  --panel: #1d1d27;
  --panel-hover: #262631;
  --text: #e6e6e6;
  --muted: #8a8a8a;
  --line: #222;
  --accent: #00ffc8;
  --danger: #ff5e83;
  --radius: 6px;
  --mono: "JetBrains Mono", monospace;
  --sans: Inter, -apple-system, BlinkMacSystemFont, sans-serif;
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  background: var(--bg);
  color: var(--text);
  font-family: var(--sans);
  min-height: 100vh;
  padding: 24px;
}

.container { max-width: 760px; margin: 0 auto; }

header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 36px;
}

.header-left { display: flex; align-items: center; gap: 12px; }
.logo { width: 60px; height: 60px; border-radius: 50%; }
h1 { font-size: 1.2rem; font-weight: 500; }

.status {
  display: flex;
  align-items: center;
  gap: 10px;
  font-family: var(--mono);
  font-size: 0.75rem;
  color: var(--accent);
}

.status-dot {
  width: 7px;
  height: 7px;
  background: var(--accent);
  border-radius: 50%;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%,100% { opacity: 1 }
  50% { opacity: 0.4 }
}

.stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 20px;
  margin-bottom: 42px;
}

.stat {
  background: var(--panel);
  padding: 18px;
  border-radius: var(--radius);
}

.stat-value {
  font-size: 1.9rem;
  font-weight: 500;
  color: var(--accent);
}

.stat-label {
  margin-top: 6px;
  font-size: 0.65rem;
  letter-spacing: 0.14em;
  color: var(--muted);
}

.section-title {
  font-family: var(--mono);
  font-size: 0.7rem;
  letter-spacing: 0.14em;
  color: var(--muted);
  margin-bottom: 16px;
}

.device-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 46px;
}

.device {
  background: var(--panel);
  padding: 14px 16px;
  display: flex;
  align-items: center;
  gap: 14px;
  border-radius: var(--radius);
  transition: background 0.15s ease;
}

.device:hover { background: var(--panel-hover); }

.device-status {
  width: 8px;
  height: 8px;
  background: var(--accent);
  border-radius: 50%;
  flex-shrink: 0;
}

.device-info { flex: 1; min-width: 0; }
.device-name { font-size: 1rem; font-weight: 500; }
.device-name.unknown { opacity: 0.6; font-style: italic; }

.device-details {
  margin-top: 3px;
  font-family: var(--mono);
  font-size: 0.7rem;
  color: var(--muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.device button { opacity: 0; pointer-events: none; }
.device:hover button { opacity: 1; pointer-events: auto; }

.btn {
  background: none;
  border: none;
  color: var(--muted);
  font-family: var(--mono);
  font-size: 0.7rem;
  padding: 6px 10px;
  border-radius: 4px;
  cursor: pointer;
}

.btn:hover { color: var(--accent); }

.history-list {
  background: var(--panel);
  border-radius: var(--radius);
  overflow: hidden;
}

.history-item {
  padding: 10px 16px;
  display: flex;
  gap: 12px;
  font-family: var(--mono);
  font-size: 0.7rem;
}

.history-item + .history-item { border-top: 1px solid var(--line); }
.history-time { min-width: 52px; color: var(--muted); }
.history-event.arrived { color: var(--accent); }
.history-event.left { color: var(--danger); }

.empty-state {
  color: var(--muted);
  padding: 20px;
  text-align: center;
  font-family: var(--mono);
  font-size: 0.75rem;
}

footer {
  margin-top: 56px;
  text-align: center;
  font-family: var(--mono);
  font-size: 0.7rem;
  color: var(--muted);
  opacity: 0.7;
}

.footer-link { color: var(--accent); text-decoration: none; }
.footer-link:hover { text-decoration: underline; }
.fish { display: inline-block; cursor: default; transition: color 0.3s ease; }
.fish:hover { color: var(--accent); }

.modal {
  display: none;
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0,0,0,0.8);
  justify-content: center;
  align-items: center;
  z-index: 1000;
}

.modal.active { display: flex; }

.modal-content {
  background: var(--panel);
  padding: 24px;
  border-radius: var(--radius);
  width: 90%;
  max-width: 360px;
}

.modal-title {
  margin-bottom: 16px;
  font-size: 1rem;
  font-weight: 500;
}

.form-group { margin-bottom: 12px; }

.form-group label {
  display: block;
  margin-bottom: 4px;
  font-family: var(--mono);
  font-size: 0.7rem;
  color: var(--muted);
}

.form-group input, .form-group select {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid var(--line);
  border-radius: 4px;
  background: var(--bg);
  color: var(--text);
  font-family: var(--sans);
  font-size: 0.9rem;
}

.form-actions { display: flex; gap: 8px; margin-top: 16px; }
.form-actions .btn { flex: 1; padding: 10px 12px; border: 1px solid var(--line); }
.btn-primary { background: var(--accent); color: var(--bg); border: none; }
.btn-primary:hover { background: #00e6b5; color: var(--bg); }
</style>
</head>
<body>
<div class="container">

<header>
  <div class="header-left">
    <img src="/static/logo.png" alt="WiFinder" class="logo">
    <h1>WiFinder</h1>
  </div>
  <div class="status">
    <span class="status-dot"></span>
    <span id="uptime">--:--:--</span>
  </div>
</header>

<div class="stats">
  <div class="stat">
    <div class="stat-value" id="online-count">-</div>
    <div class="stat-label">ONLINE</div>
  </div>
  <div class="stat">
    <div class="stat-value" id="known-count">-</div>
    <div class="stat-label">KNOWN</div>
  </div>
  <div class="stat">
    <div class="stat-value" id="arrivals-today">-</div>
    <div class="stat-label">ARRIVALS</div>
  </div>
</div>

<h2 class="section-title">WHO'S HOME</h2>
<div class="device-list" id="device-list">
  <div class="empty-state">scanning...</div>
</div>

<h2 class="section-title">RECENT ACTIVITY</h2>
<div class="history-list" id="history-list">
  <div class="empty-state">no activity yet</div>
</div>

<div id="hidden-section" style="display: none; margin-top: 42px;">
  <h2 class="section-title" style="opacity: 0.5;">HIDDEN</h2>
  <div class="device-list" id="hidden-list"></div>
</div>

<footer>
  <a href="https://github.com/mpescimoro/wi-finder" class="footer-link">github</a>
  · v2.0 ·
  <span class="fish" title="p3sc1">&lt;°))&gt;&lt;</span>
</footer>

</div>

<div class="modal" id="edit-modal">
  <div class="modal-content">
    <h3 class="modal-title">Edit device</h3>
    <form id="edit-form">
      <input type="hidden" id="edit-mac">
      <div class="form-group">
        <label for="edit-name">NAME</label>
        <input type="text" id="edit-name" placeholder="e.g. Marco's iPhone">
      </div>
      <div class="form-group">
        <label for="edit-group">GROUP</label>
        <select id="edit-group">
          <option value="">no group</option>
          <option value="family">family</option>
          <option value="guests">guests</option>
          <option value="iot">iot</option>
          <option value="work">work</option>
          <option value="hidden">hidden</option>
        </select>
      </div>
      <div class="form-actions">
        <button type="button" class="btn" onclick="closeModal()">cancel</button>
        <button type="submit" class="btn btn-primary">save</button>
      </div>
    </form>
  </div>
</div>

<script>
let startedAt = null;

function formatUptime(seconds) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  return [h, m, s].map(n => n.toString().padStart(2, '0')).join(':');
}

function updateUptime() {
  if (startedAt) {
    const elapsed = Math.floor((Date.now() - startedAt) / 1000);
    document.getElementById('uptime').textContent = formatUptime(elapsed);
  }
}

function updateData() {
  fetch('/api/status')
    .then(r => r.json())
    .then(data => {
      if (!startedAt && data.started_at) {
        startedAt = data.started_at * 1000;
      }
      
      document.getElementById('online-count').textContent = data.online_count;
      document.getElementById('known-count').textContent = data.known_count;
      document.getElementById('arrivals-today').textContent = data.arrivals_today;

      const deviceList = document.getElementById('device-list');
      const hiddenList = document.getElementById('hidden-list');
      const hiddenSection = document.getElementById('hidden-section');
      
      const visibleDevices = data.devices.filter(d => d.group !== 'hidden');
      const hiddenDevices = data.devices.filter(d => d.group === 'hidden');
      
      const renderDevice = d => `
        <div class="device">
          <div class="device-status"></div>
          <div class="device-info">
            <div class="device-name ${d.name ? '' : 'unknown'}">${d.name || 'unknown'}${d.group && d.group !== 'hidden' ? ' <span style="opacity:0.5;font-size:0.8em">(' + d.group + ')</span>' : ''}</div>
            <div class="device-details">${d.mac} · ${d.vendor || 'unknown'} · ${d.ip || '-'}</div>
          </div>
          <button class="btn" onclick="editDevice('${d.mac}', '${(d.name || '').replace(/'/g, "\\\\'")}', '${d.group || ''}')">edit</button>
        </div>
      `;
      
      if (visibleDevices.length === 0) {
        deviceList.innerHTML = '<div class="empty-state">no devices online</div>';
      } else {
        deviceList.innerHTML = visibleDevices.map(renderDevice).join('');
      }
      
      if (hiddenDevices.length > 0) {
        hiddenSection.style.display = 'block';
        hiddenList.innerHTML = hiddenDevices.map(renderDevice).join('');
      } else {
        hiddenSection.style.display = 'none';
      }

      const historyList = document.getElementById('history-list');
      if (data.history.length === 0) {
        historyList.innerHTML = '<div class="empty-state">no activity yet</div>';
      } else {
        historyList.innerHTML = data.history.map(h => `
          <div class="history-item">
            <span class="history-time">${h.time}</span>
            <span class="history-event ${h.event_type}">${h.device_name || h.mac} ${h.event_type}</span>
          </div>
        `).join('');
      }
    });
}

function editDevice(mac, name, group) {
  document.getElementById('edit-mac').value = mac;
  document.getElementById('edit-name').value = name;
  document.getElementById('edit-group').value = group;
  document.getElementById('edit-modal').classList.add('active');
}

function closeModal() {
  document.getElementById('edit-modal').classList.remove('active');
}

document.getElementById('edit-form').addEventListener('submit', function(e) {
  e.preventDefault();
  const mac = document.getElementById('edit-mac').value;
  const name = document.getElementById('edit-name').value;
  const group = document.getElementById('edit-group').value;

  fetch('/api/device/' + encodeURIComponent(mac), {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({name: name, group: group})
  }).then(() => {
    closeModal();
    updateData();
  });
});

document.getElementById('edit-modal').addEventListener('click', function(e) {
  if (e.target === this) closeModal();
});

updateData();
setInterval(updateData, 10000);
setInterval(updateUptime, 1000);
</script>
</body>
</html>"""


def create_app(config: Config) -> Flask:
    """Create the Flask application."""
    app = Flask(__name__)

    db = Database(config.db_path)
    watcher = Watcher(config, db)
    started_at = time.time()

    def background_scan():
        while True:
            try:
                watcher.scan_once()
            except Exception as e:
                print(f"Scan error: {e}")
            time.sleep(config.interval)

    scanner_thread = threading.Thread(target=background_scan, daemon=True)
    scanner_thread.start()

    @app.route("/")
    def index():
        return render_template_string(HTML_TEMPLATE)

    @app.route("/static/<path:filename>")
    def static_files(filename):
        return send_from_directory(STATIC_DIR, filename)

    @app.route("/api/status")
    def api_status():
        online = db.get_online_devices()
        all_devices = db.get_all_devices()
        history = db.get_history(limit=10)

        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_history = db.get_history(limit=1000, since=today_start)
        arrivals_today = len([h for h in today_history if h.event_type == "arrived"])

        return jsonify({
            "online_count": len(online),
            "known_count": len(all_devices),
            "arrivals_today": arrivals_today,
            "started_at": started_at,
            "devices": [
                {
                    "mac": d.mac,
                    "name": d.name,
                    "vendor": d.vendor,
                    "ip": d.ip,
                    "group": d.group,
                }
                for d in online
            ],
            "history": [
                {
                    "mac": h.mac,
                    "event_type": h.event_type,
                    "time": h.timestamp.strftime("%H:%M"),
                    "device_name": h.device_name,
                }
                for h in history
            ],
        })

    @app.route("/api/device/<mac>", methods=["POST"])
    def api_update_device(mac):
        data = request.get_json()
        if "name" in data:
            db.set_device_name(mac, data["name"])
        if "group" in data:
            db.set_device_group(mac, data["group"])
        return jsonify({"status": "ok"})

    @app.route("/api/who")
    def api_who():
        return jsonify({"summary": watcher.get_summary()})

    return app
