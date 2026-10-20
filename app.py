from flask import Flask, jsonify, render_template_string
import os
import subprocess
import sqlite3
import threading
import time
import requests
from datetime import datetime

app = Flask(__name__)

# --- Config (env vars; overrides keep local/prod flexible) ---
DB = os.environ.get("NUT_UI_DB", os.path.join(os.path.dirname(os.path.abspath(__file__)), "events.db"))
UPS_NAME = os.environ.get("UPS_NAME", "eaton")
UPS_HOST = os.environ.get("UPS_HOST", "").strip()  # empty = local upsd; else host/IP for upsc name@host
LISTEN_HOST = os.environ.get("LISTEN_HOST", "0.0.0.0")
LISTEN_PORT = int(os.environ.get("LISTEN_PORT", "8765"))
SITE_TITLE = os.environ.get("SITE_TITLE", "UPS Monitor")

NTFY_URL = os.environ.get("NTFY_URL", "")
NTFY_USER = os.environ.get("NTFY_USER", "")
NTFY_PASS = os.environ.get("NTFY_PASS", "")
NTFY_TITLE = os.environ.get("NTFY_TITLE", "UPS")


def ups_target():
    """Build upsc target: name or name@host."""
    if UPS_HOST:
        return f"{UPS_NAME}@{UPS_HOST}"
    return UPS_NAME


def notify(msg, priority="high", tags=""):
    if not NTFY_URL:
        print(f"[NOTIFY SKIP] NTFY_URL not set — {msg}")
        return False
    try:
        headers = {"Title": NTFY_TITLE, "Priority": priority, "Tags": tags}
        auth = (NTFY_USER, NTFY_PASS) if NTFY_USER else None
        r = requests.post(
            NTFY_URL,
            data=msg.encode("utf-8"),
            headers=headers,
            auth=auth,
            timeout=5,
        )
        return r.status_code == 200
    except Exception as e:
        print(f"[NOTIFY ERROR] {e}")
        return False


def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute(
        """CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT,
        message TEXT
    )"""
    )
    conn.commit()
    conn.close()


def log_event(msg):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute(
        "INSERT INTO events (ts, message) VALUES (?, ?)",
        (datetime.now().strftime("%d/%m %H:%M:%S"), msg),
    )
    conn.commit()
    conn.close()
    print(f"[EVENT] {msg}")


def get_ups_data():
    try:
        result = subprocess.run(
            ["upsc", ups_target()],
            capture_output=True,
            text=True,
            timeout=5,
        )
        data = {}
        for line in result.stdout.splitlines():
            if ": " in line:
                k, v = line.split(": ", 1)
                data[k.strip()] = v.strip()
        return data
    except Exception:
        return {}


last_status = {"status": "OL", "last_warn": 0}


def monitor():
    while True:
        data = get_ups_data()
        status = data.get("ups.status", "")
        charge = data.get("battery.charge", "?")
        runtime = int(data.get("battery.runtime", 0) or 0) // 60

        if "OB" in status and last_status["status"] != "OB":
            msg = f"⚡ Coupure secteur - Batterie {charge}%"
            log_event(msg)
            notify(msg, priority="high", tags="warning,zap")
            last_status["status"] = "OB"
            last_status["last_warn"] = time.time()

        elif "OB" in status:
            if time.time() - last_status["last_warn"] >= 300:
                msg = f"🔋 Sur batterie - {charge}% - ~{runtime} min restantes"
                log_event(msg)
                notify(msg, priority="default", tags="battery")
                last_status["last_warn"] = time.time()

        elif "OL" in status and last_status["status"] == "OB":
            msg = f"✅ Secteur rétabli - Batterie {charge}%"
            log_event(msg)
            notify(msg, priority="default", tags="white_check_mark")
            last_status["status"] = "OL"

        elif "LB" in status:
            msg = f"🔴 Batterie faible ! Shutdown imminent - {charge}%"
            log_event(msg)
            notify(msg, priority="urgent", tags="rotating_light,skull")

        time.sleep(10)


@app.route("/")
def index():
    return render_template_string(HTML, site_title=SITE_TITLE)


@app.route("/api/status")
def api_status():
    return jsonify(get_ups_data())


@app.route("/api/events")
def api_events():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT ts, message FROM events ORDER BY id DESC LIMIT 100")
    rows = [{"ts": r[0], "message": r[1]} for r in c.fetchall()]
    conn.close()
    return jsonify(rows)


@app.route("/api/test-notify")
def test_notify():
    msg = f"🧪 Test notification - {datetime.now().strftime('%d/%m %H:%M:%S')}"
    ok = notify(msg, priority="default", tags="test_tube")
    log_event(msg)
    return jsonify({"sent": ok, "message": msg})


HTML = """
<!DOCTYPE html>
<html lang="fr">
<head>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>⚡</text></svg>">
<meta charset="UTF-8">
<title>{{ site_title }}</title>
<meta http-equiv="refresh" content="10">
<style>
  body { font-family: monospace; background: #1a1a2e; color: #eee; padding: 20px; }
  h1 { color: #00d4ff; }
  .card { background: #16213e; border-radius: 8px; padding: 15px; margin: 10px 0; }
  .card h2 { color: #00d4ff; font-size: 15px; margin: 0 0 12px 0; }
  .status-ol { color: #00ff88; font-weight: bold; }
  .status-ob { color: #ff6b35; font-weight: bold; }
  .status-lb { color: #ff0000; font-weight: bold; }
  .bar-bg { background: #333; border-radius: 4px; height: 24px; width: 100%; margin-top: 5px; }
  .bar-fill { height: 24px; border-radius: 4px; background: #00ff88; transition: width 0.5s; display: flex; align-items: center; padding-left: 8px; font-size: 13px; color: #000; font-weight: bold; }
  table { width: 100%; border-collapse: collapse; }
  td { padding: 6px 10px; border-bottom: 1px solid #333; }
  td:first-child { color: #aaa; width: 220px; }
  .events { max-height: 400px; overflow-y: auto; }
  .event-row { padding: 5px 0; border-bottom: 1px solid #222; font-size: 13px; }
  .event-ts { color: #888; margin-right: 10px; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; }
  .badge-on { background: #003322; color: #00ff88; }
  .badge-off { background: #330000; color: #ff6666; }
</style>
</head>
<body>
<h1>🔋 {{ site_title }}
  <button id="testBtn" onclick="testNotify()" style="
    float:right;
    background:#00d4ff;
    color:#000;
    border:none;
    padding:8px 16px;
    border-radius:6px;
    font-family:monospace;
    font-weight:bold;
    font-size:14px;
    cursor:pointer;
  ">🧪 Tester notif</button>
</h1>
<div id="content">Chargement...</div>

<script>
async function refresh() {
  const [status, events] = await Promise.all([
    fetch('/api/status').then(r => r.json()),
    fetch('/api/events').then(r => r.json())
  ]);

  const s = status['ups.status'] || '?';
  const charge = parseInt(status['battery.charge'] || 0);
  const runtime = Math.floor(parseInt(status['battery.runtime'] || 0) / 60);
  const power = status['ups.realpower'] || '?';
  const load = status['ups.load'] || '?';
  const voltage = status['output.voltage'] || '?';
  const model = status['ups.model'] || '?';

  let statusClass = 'status-ol';
  let statusLabel = '✅ Sur secteur (OL)';
  if (s.includes('OB')) { statusClass = 'status-ob'; statusLabel = '⚡ Sur batterie (OB)'; }
  if (s.includes('LB')) { statusClass = 'status-lb'; statusLabel = '🔴 Batterie faible (LB)'; }

  const barColor = charge > 50 ? '#00ff88' : charge > 20 ? '#ffaa00' : '#ff3333';

  const chargeLow     = status['battery.charge.low'] || '?';
  const delayShutdown = status['ups.delay.shutdown'] || '?';
  const delayStart    = status['ups.delay.start'] || '?';
  const transferHigh  = status['input.transfer.high'] || '?';
  const transferLow   = status['input.transfer.low'] || '?';
  const nomPower      = status['ups.power.nominal'] || '?';
  const nomVoltage    = status['output.voltage.nominal'] || '?';
  const nomFreq       = status['output.frequency.nominal'] || '?';
  const beeper        = status['ups.beeper.status'] || '?';
  const firmware      = status['ups.firmware'] || '?';
  const driver        = status['driver.name'] || '?';
  const pollInterval  = status['driver.parameter.pollinterval'] || '?';

  const outlet1 = status['outlet.1.status'] || '?';
  const outlet2 = status['outlet.2.status'] || '?';

  const badgeOutlet1 = outlet1 === 'on'
    ? '<span class="badge badge-on">ON</span>'
    : '<span class="badge badge-off">OFF</span>';
  const badgeOutlet2 = outlet2 === 'on'
    ? '<span class="badge badge-on">ON</span>'
    : '<span class="badge badge-off">OFF</span>';
  const badgeBeeper = beeper === 'enabled'
    ? '<span class="badge badge-on">activé</span>'
    : '<span class="badge badge-off">désactivé</span>';

  let html = `
    <div class="card">
      <h2>📊 Statut temps réel</h2>
      <table>
        <tr><td>Modèle</td><td>${model}</td></tr>
        <tr><td>Statut</td><td><span class="${statusClass}">${statusLabel}</span></td></tr>
        <tr><td>Tension sortie</td><td>${voltage} V</td></tr>
        <tr><td>Charge</td><td>${load}% — ${power} W</td></tr>
        <tr><td>Autonomie restante</td><td>${runtime} min</td></tr>
        <tr><td>Niveau batterie</td><td>
          <div class="bar-bg"><div class="bar-fill" style="width:${charge}%;background:${barColor}">${charge}%</div></div>
        </td></tr>
      </table>
    </div>

    <div class="card">
      <h2>⚙️ Paramétrage UPS</h2>
      <table>
        <tr><td>Puissance nominale</td><td>${nomPower} VA</td></tr>
        <tr><td>Tension nominale</td><td>${nomVoltage} V</td></tr>
        <tr><td>Fréquence nominale</td><td>${nomFreq} Hz</td></tr>
        <tr><td>Seuil batterie faible</td><td>${chargeLow}%</td></tr>
        <tr><td>Délai extinction (shutdown)</td><td>${delayShutdown} s</td></tr>
        <tr><td>Délai redémarrage (start)</td><td>${delayStart} s</td></tr>
        <tr><td>Plage tension entrée</td><td>${transferLow} – ${transferHigh} V</td></tr>
        <tr><td>Buzzer</td><td>${badgeBeeper}</td></tr>
        <tr><td>Prise PowerShare 1</td><td>${badgeOutlet1}</td></tr>
        <tr><td>Prise PowerShare 2</td><td>${badgeOutlet2}</td></tr>
        <tr><td>Firmware</td><td>${firmware}</td></tr>
        <tr><td>Driver</td><td>${driver} (poll: ${pollInterval}s)</td></tr>
      </table>
    </div>

    <div class="card">
      <h2>📋 Événements</h2>
      <div class="events">
  `;

  if (events.length === 0) {
    html += '<div class="event-row" style="color:#666">Aucun événement enregistré</div>';
  } else {
    for (const e of events) {
      html += `<div class="event-row"><span class="event-ts">${e.ts}</span>${e.message}</div>`;
    }
  }

  html += '</div></div>';
  document.getElementById('content').innerHTML = html;
}

async function testNotify() {
  const btn = document.getElementById('testBtn');
  const originalText = btn.innerText;
  btn.innerText = '⏳ Envoi...';
  btn.disabled = true;

  try {
    const res = await fetch('/api/test-notify');
    const data = await res.json();

    if (data.sent) {
      btn.innerText = '✅ Envoyé !';
      btn.style.background = '#00ff88';
    } else {
      btn.innerText = '❌ Échec';
      btn.style.background = '#ff3333';
    }
  } catch (e) {
    btn.innerText = '❌ Erreur';
    btn.style.background = '#ff3333';
  }

  setTimeout(() => {
    btn.innerText = originalText;
    btn.style.background = '#00d4ff';
    btn.disabled = false;
    refresh();
  }, 2000);
}

refresh();
setInterval(refresh, 10000);
</script>
</body>
</html>
"""

if __name__ == "__main__":
    init_db()
    notify("🟢 nut-ui démarré - monitoring actif", tags="rocket")
    t = threading.Thread(target=monitor, daemon=True)
    t.start()
    app.run(host=LISTEN_HOST, port=LISTEN_PORT)
