# nut-ui

Lightweight web UI and notifier for [Network UPS Tools (NUT)](https://networkupstools.org/).

Polls your UPS with `upsc`, shows live status in the browser, stores power events in SQLite, and can push alerts to [ntfy](https://ntfy.sh/).

## Features

- Live UPS status (online / on battery / low battery)
- Battery charge, load, runtime, voltage + settings summary
- Event history (SQLite)
- Optional ntfy alerts (power loss, periodic on-battery, restore, low battery)
- **Dark / light** themes (modern UI; light theme uses soft gray, not pure white)
- **English / French** UI (choice saved in the browser)
- Configurable **refresh interval** (5 / 10 / 30 / 60 s) with **in-place** value updates (no full-page flicker)
- Config via **`.env`** (or `/etc/nut-ui/nut-ui.env`) so settings survive git updates
- Docker image on GHCR + host install script

## Prerequisites

1. **NUT** installed and working (`upsc <upsname>` returns data).
2. Python **3.10+** (host install) **or** Docker.

```bash
# Debian / Ubuntu examples
sudo apt update
sudo apt install nut          # full stack on the UPS host
# or, client-only against a remote upsd:
sudo apt install nut-client
upsc myups                    # or: upsc myups@192.168.1.1
```

## Quick start — host (recommended on the NUT machine)

```bash
curl -fsSL https://raw.githubusercontent.com/ElPaul0/nut-ui/main/scripts/install-host.sh | sudo bash
sudo nano /etc/nut-ui/nut-ui.env    # set UPS_NAME (and UPS_HOST if needed)
sudo systemctl restart nut-ui
```

Open `http://<host>:8765/`.

**What stays persistent across updates**

| Path | Purpose |
|------|---------|
| `/etc/nut-ui/nut-ui.env` | Your configuration (not overwritten on update) |
| `/var/lib/nut-ui/events.db` | Event history |
| `/opt/nut-ui` | App code (updated with `git pull` via the install script) |

Update:

```bash
sudo bash /opt/nut-ui/scripts/install-host.sh
```

### Manual host install

```bash
git clone https://github.com/ElPaul0/nut-ui.git /opt/nut-ui
cd /opt/nut-ui
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
sudo mkdir -p /etc/nut-ui /var/lib/nut-ui
sudo cp .env.example /etc/nut-ui/nut-ui.env
sudo nano /etc/nut-ui/nut-ui.env
sudo cp deploy/nut-ui.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now nut-ui
```

`python-dotenv` also loads a local `.env` in the app directory if present (gitignored).

## Docker

Use when the container can reach `upsd` on the network (`UPS_HOST`).

```bash
git clone https://github.com/ElPaul0/nut-ui.git
cd nut-ui
cp .env.example .env
# edit .env → UPS_NAME, UPS_HOST, optional ntfy
docker compose up -d
```

One-liner:

```bash
docker run -d --name nut-ui --restart unless-stopped \
  -p 8765:8765 \
  -e UPS_NAME=ups \
  -e UPS_HOST=192.168.1.1 \
  -e DEFAULT_LANG=en \
  -v nut-ui-data:/data \
  ghcr.io/elpaul0/nut-ui:latest
```

Image: [`ghcr.io/elpaul0/nut-ui`](https://github.com/ElPaul0/nut-ui/pkgs/container/nut-ui)

> On many homelabs NUT runs on the hypervisor. Prefer the host install there; Docker is ideal when `upsd` listens on the LAN.

## Configuration

Copy `.env.example` → `.env` or `/etc/nut-ui/nut-ui.env`.

| Variable | Default | Description |
|----------|---------|-------------|
| `UPS_NAME` | `ups` | Name from NUT `ups.conf` |
| `UPS_HOST` | _(empty)_ | Remote `upsd` → `upsc name@host` |
| `LISTEN_HOST` | `0.0.0.0` | Bind address |
| `LISTEN_PORT` | `8765` | HTTP port |
| `SITE_TITLE` | `UPS Monitor` | Page title |
| `DEFAULT_LANG` | `en` | Initial UI language (`en` / `fr`) |
| `DEFAULT_THEME` | `dark` | Initial theme (`dark` / `light`) |
| `DEFAULT_REFRESH_SEC` | `10` | Initial UI refresh (`5` / `10` / `30` / `60`) |
| `NOTIFY_LANG` | same as `DEFAULT_LANG` | Language for ntfy / logged events |
| `NUT_UI_DB` | `./events.db` | SQLite path |
| `NTFY_URL` | _(empty)_ | Full topic URL; empty disables notifications |
| `NTFY_USER` / `NTFY_PASS` | _(empty)_ | Optional ntfy auth |
| `NTFY_TITLE` | `UPS` | Notification title |

Theme, language, and refresh interval chosen in the UI are stored in **browser `localStorage`** and override the defaults.

## API

| Endpoint | Description |
|----------|-------------|
| `GET /` | Web UI |
| `GET /api/status` | Raw `upsc` JSON (`_error` on failure) |
| `GET /api/events` | Last 100 events |
| `GET /api/test-notify` | Send a test ntfy message |
| `GET /api/health` | Liveness + UPS reachability |
| `GET /api/config` | Public UI defaults (no secrets) |

## License

MIT
