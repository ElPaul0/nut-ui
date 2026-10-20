#!/usr/bin/env bash
# Install nut-ui on a Linux host (same machine as NUT, or with UPS_HOST set).
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/nut-ui}"
ENV_FILE="${ENV_FILE:-/etc/nut-ui/nut-ui.env}"
DATA_DIR="${DATA_DIR:-/var/lib/nut-ui}"
REPO_URL="${REPO_URL:-https://github.com/ElPaul0/nut-ui.git}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root (sudo)." >&2
  exit 1
fi

echo "==> Checking NUT client (upsc)"
if ! command -v upsc >/dev/null 2>&1; then
  echo "upsc not found. Install NUT first, for example:"
  echo "  Debian/Ubuntu: apt install nut-client   # or nut (full stack)"
  echo "  Then configure ups.conf / upsd and verify: upsc <ups_name>"
  exit 1
fi

echo "==> Installing app into ${APP_DIR}"
if [[ -d "${APP_DIR}/.git" ]]; then
  git -C "${APP_DIR}" pull --ff-only
else
  mkdir -p "$(dirname "${APP_DIR}")"
  git clone "${REPO_URL}" "${APP_DIR}"
fi

python3 -m venv "${APP_DIR}/.venv"
"${APP_DIR}/.venv/bin/pip" install --upgrade pip
"${APP_DIR}/.venv/bin/pip" install -r "${APP_DIR}/requirements.txt"

mkdir -p "$(dirname "${ENV_FILE}")" "${DATA_DIR}"
if [[ ! -f "${ENV_FILE}" ]]; then
  cp "${APP_DIR}/.env.example" "${ENV_FILE}"
  # Point DB to persistent data dir
  if grep -q '^NUT_UI_DB=' "${ENV_FILE}"; then
    sed -i "s|^NUT_UI_DB=.*|NUT_UI_DB=${DATA_DIR}/events.db|" "${ENV_FILE}"
  else
    echo "NUT_UI_DB=${DATA_DIR}/events.db" >> "${ENV_FILE}"
  fi
  echo "Created ${ENV_FILE} — edit UPS_NAME / UPS_HOST / ntfy before starting."
else
  echo "Keeping existing ${ENV_FILE} (survives updates)."
fi

install -m 644 "${APP_DIR}/deploy/nut-ui.service" /etc/systemd/system/nut-ui.service
# Ensure unit points at ENV_FILE
sed -i "s|^EnvironmentFile=.*|EnvironmentFile=-${ENV_FILE}|" /etc/systemd/system/nut-ui.service

systemctl daemon-reload
systemctl enable --now nut-ui.service
systemctl --no-pager --full status nut-ui.service || true

echo
echo "Done."
echo "  Config : ${ENV_FILE}"
echo "  Data   : ${DATA_DIR}"
echo "  App    : ${APP_DIR}"
echo "  Health : curl -s http://127.0.0.1:8765/api/health"
echo
echo "Update later with:  sudo APP_DIR=${APP_DIR} $0"
echo "(git pull + pip install; ${ENV_FILE} is left untouched)"
