# nut-ui

Lightweight web UI and notifier for [Network UPS Tools (NUT)](https://networkupstools.org/).

It polls your UPS with `upsc`, shows live status in a simple browser page, stores power events in SQLite, and can push alerts to [ntfy](https://ntfy.sh/).

## Features

- Live UPS status (line / battery / low battery)
- Battery charge bar, load, runtime, voltage
- UPS settings summary (delays, transfer voltages, PowerShare outlets, firmware, …)
- Event history (SQLite)
- Optional ntfy notifications on power loss, battery warnings, and recovery
- Manual “test notification” button

## Requirements

- Python 3.10+
- NUT client tools (`upsc` on `PATH`)
- A reachable NUT device (`upsc <name>` or `upsc <name>@<host>`)

## Docker (one-liner)

Needs network access to a NUT `upsd` (set `UPS_HOST` to that host/IP):

```bash
docker run -d --name nut-ui --restart unless-stopped \
  -p 8765:8765 \
  -e UPS_NAME=eaton \
  -e UPS_HOST=192.168.1.1 \
  -e SITE_TITLE="UPS Monitor" \
  -v nut-ui-data:/data \
  ghcr.io/elpaul0/nut-ui:latest
```

Or with Compose (see `docker-compose.yml`):

```bash
docker compose up -d
```

Image: [`ghcr.io/elpaul0/nut-ui`](https://github.com/ElPaul0/nut-ui/pkgs/container/nut-ui) (built on every push to `main`).

> Running on a separate Docker host only works if that host can reach `upsd` over the network (`LISTEN` in `upsd.conf` / firewall). On many homelabs NUT stays on the hypervisor; native install is then simpler.

## Quick start (host install)

```bash
git clone https://github.com/ElPaul0/nut-ui.git
cd nut-ui
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # edit as needed
export $(grep -v '^#' .env | xargs)   # or use your preferred env loader
python app.py
```

Open `http://<host>:8765/`.

### systemd example

```ini
[Unit]
Description=NUT Web UI
After=network.target nut-server.service

[Service]
WorkingDirectory=/opt/nut-ui
EnvironmentFile=/opt/nut-ui/.env
ExecStart=/usr/bin/python3 /opt/nut-ui/app.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `UPS_NAME` | `eaton` | UPS name from NUT `ups.conf` |
| `UPS_HOST` | _(empty)_ | Optional remote `upsd` host → uses `upsc name@host` |
| `LISTEN_HOST` | `0.0.0.0` | Bind address |
| `LISTEN_PORT` | `8765` | HTTP port |
| `SITE_TITLE` | `UPS Monitor` | Page title |
| `NUT_UI_DB` | `./events.db` | SQLite database path |
| `NTFY_URL` | _(empty)_ | Full ntfy topic URL (notifications disabled if unset) |
| `NTFY_USER` / `NTFY_PASS` | _(empty)_ | Optional basic auth for ntfy |
| `NTFY_TITLE` | `UPS` | Notification title |

## API

| Endpoint | Description |
|----------|-------------|
| `GET /` | Web UI |
| `GET /api/status` | Raw `upsc` key/value JSON |
| `GET /api/events` | Last 100 events |
| `GET /api/test-notify` | Send a test ntfy message and log it |

## Notes

- Best run on the same host as NUT (or with network access to `upsd`).
- Notifications are skipped when `NTFY_URL` is not set.
- UI strings are currently in French; configuration and docs are in English.

## License

MIT
