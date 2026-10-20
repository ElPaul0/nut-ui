"""nut-ui — web UI and ntfy alerts for Network UPS Tools."""

from __future__ import annotations

import os
import sqlite3
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path

import requests
from flask import Flask, jsonify, render_template, send_from_directory

try:
    from dotenv import load_dotenv
except ImportError:  # optional at runtime if not installed
    load_dotenv = None

BASE_DIR = Path(__file__).resolve().parent

# Load persistent .env next to the app (survives git pulls if .env is outside or gitignored)
if load_dotenv:
    load_dotenv(BASE_DIR / ".env", override=False)

app = Flask(__name__, template_folder="templates", static_folder="static")

# --- Config ---
DB = Path(os.environ.get("NUT_UI_DB", str(BASE_DIR / "events.db")))
UPS_NAME = os.environ.get("UPS_NAME", "ups")
UPS_HOST = os.environ.get("UPS_HOST", "").strip()
LISTEN_HOST = os.environ.get("LISTEN_HOST", "0.0.0.0")
LISTEN_PORT = int(os.environ.get("LISTEN_PORT", "8765"))
SITE_TITLE = os.environ.get("SITE_TITLE", "UPS Monitor")
DEFAULT_LANG = os.environ.get("DEFAULT_LANG", "en").lower()
if DEFAULT_LANG not in ("en", "fr"):
    DEFAULT_LANG = "en"
NOTIFY_LANG = os.environ.get("NOTIFY_LANG", DEFAULT_LANG).lower()
if NOTIFY_LANG not in ("en", "fr"):
    NOTIFY_LANG = DEFAULT_LANG
DEFAULT_THEME = os.environ.get("DEFAULT_THEME", "dark").lower()
if DEFAULT_THEME not in ("dark", "light"):
    DEFAULT_THEME = "dark"
try:
    DEFAULT_REFRESH_SEC = int(os.environ.get("DEFAULT_REFRESH_SEC", "10"))
except ValueError:
    DEFAULT_REFRESH_SEC = 10
if DEFAULT_REFRESH_SEC not in (5, 10, 30, 60):
    DEFAULT_REFRESH_SEC = 10

NTFY_URL = os.environ.get("NTFY_URL", "").strip()
NTFY_USER = os.environ.get("NTFY_USER", "")
NTFY_PASS = os.environ.get("NTFY_PASS", "")
NTFY_TITLE = os.environ.get("NTFY_TITLE", "UPS")

# --- i18n for server-side notifications / events ---
MSG = {
    "en": {
        "started": "nut-ui started — monitoring active",
        "power_loss": "Power failure — battery {charge}%",
        "on_battery": "On battery — {charge}% — ~{runtime} min left",
        "power_restored": "Mains restored — battery {charge}%",
        "low_battery": "Low battery! Shutdown imminent — {charge}%",
        "test": "Test notification — {ts}",
    },
    "fr": {
        "started": "nut-ui démarré — monitoring actif",
        "power_loss": "Coupure secteur — batterie {charge}%",
        "on_battery": "Sur batterie — {charge}% — ~{runtime} min restantes",
        "power_restored": "Secteur rétabli — batterie {charge}%",
        "low_battery": "Batterie faible ! Shutdown imminent — {charge}%",
        "test": "Test notification — {ts}",
    },
}


def t(key: str, **kwargs) -> str:
    lang = NOTIFY_LANG if NOTIFY_LANG in MSG else "en"
    template = MSG[lang].get(key) or MSG["en"].get(key, key)
    return template.format(**kwargs)


def ups_target() -> str:
    if UPS_HOST:
        return f"{UPS_NAME}@{UPS_HOST}"
    return UPS_NAME


def notify(msg: str, priority: str = "high", tags: str = "") -> bool:
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


def init_db() -> None:
    DB.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB) as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT,
                message TEXT
            )"""
        )


def log_event(msg: str) -> None:
    with sqlite3.connect(DB) as conn:
        conn.execute(
            "INSERT INTO events (ts, message) VALUES (?, ?)",
            (datetime.now().strftime("%d/%m %H:%M:%S"), msg),
        )
    print(f"[EVENT] {msg}")


def get_ups_data() -> dict:
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
        if result.returncode != 0 and not data:
            data["_error"] = (result.stderr or result.stdout or "upsc failed").strip()
        return data
    except FileNotFoundError:
        return {"_error": "upsc not found — install NUT client tools"}
    except Exception as e:
        return {"_error": str(e)}


last_status = {"status": "OL", "last_warn": 0.0}


def monitor() -> None:
    while True:
        data = get_ups_data()
        status = data.get("ups.status", "")
        charge = data.get("battery.charge", "?")
        try:
            runtime = int(data.get("battery.runtime", 0) or 0) // 60
        except ValueError:
            runtime = 0

        if "OB" in status and last_status["status"] != "OB":
            msg = t("power_loss", charge=charge)
            log_event(msg)
            notify(msg, priority="high", tags="warning,zap")
            last_status["status"] = "OB"
            last_status["last_warn"] = time.time()

        elif "OB" in status:
            if time.time() - last_status["last_warn"] >= 300:
                msg = t("on_battery", charge=charge, runtime=runtime)
                log_event(msg)
                notify(msg, priority="default", tags="battery")
                last_status["last_warn"] = time.time()

        elif "OL" in status and last_status["status"] == "OB":
            msg = t("power_restored", charge=charge)
            log_event(msg)
            notify(msg, priority="default", tags="white_check_mark")
            last_status["status"] = "OL"

        elif "LB" in status:
            msg = t("low_battery", charge=charge)
            log_event(msg)
            notify(msg, priority="urgent", tags="rotating_light,skull")

        time.sleep(10)


@app.route("/")
def index():
    return render_template(
        "index.html",
        site_title=SITE_TITLE,
        default_lang=DEFAULT_LANG,
        default_theme=DEFAULT_THEME,
        default_refresh_sec=DEFAULT_REFRESH_SEC,
    )


@app.route("/api/status")
def api_status():
    return jsonify(get_ups_data())


@app.route("/api/events")
def api_events():
    with sqlite3.connect(DB) as conn:
        rows = conn.execute(
            "SELECT ts, message FROM events ORDER BY id DESC LIMIT 100"
        ).fetchall()
    return jsonify([{"ts": r[0], "message": r[1]} for r in rows])


@app.route("/api/test-notify")
def test_notify():
    msg = t("test", ts=datetime.now().strftime("%d/%m %H:%M:%S"))
    ok = notify(msg, priority="default", tags="test_tube")
    log_event(msg)
    return jsonify({"sent": ok, "message": msg})


@app.route("/api/health")
def api_health():
    data = get_ups_data()
    ok = "ups.status" in data and "_error" not in data
    return jsonify(
        {
            "ok": ok,
            "ups_target": ups_target(),
            "ntfy_configured": bool(NTFY_URL),
            "error": data.get("_error"),
        }
    ), (200 if ok else 503)


@app.route("/api/config")
def api_config():
    """Public, non-secret UI defaults."""
    return jsonify(
        {
            "site_title": SITE_TITLE,
            "default_lang": DEFAULT_LANG,
            "default_theme": DEFAULT_THEME,
            "default_refresh_sec": DEFAULT_REFRESH_SEC,
            "ntfy_configured": bool(NTFY_URL),
            "ups_target": ups_target(),
        }
    )


@app.route("/favicon.ico")
def favicon():
    return send_from_directory(
        app.static_folder, "favicon.svg", mimetype="image/svg+xml"
    )


def main() -> None:
    init_db()
    print(f"[nut-ui] UPS target: {ups_target()}")
    print(f"[nut-ui] Listening on http://{LISTEN_HOST}:{LISTEN_PORT}")
    notify(t("started"), tags="rocket")
    threading.Thread(target=monitor, daemon=True).start()
    app.run(host=LISTEN_HOST, port=LISTEN_PORT)


if __name__ == "__main__":
    main()
