#!/usr/bin/env bash

set -euo pipefail

APP_DIR="${1:?Application directory is required}"
PM2_APP_NAME="${2:?PM2 application name is required}"
BACKEND_DIR="${APP_DIR}/rag-app/backend"
VENV_DIR="${BACKEND_DIR}/.venv"

# Preserve the existing production environment while new installations use .venv.
if [[ ! -x "${VENV_DIR}/bin/python" && -x "${BACKEND_DIR}/venv/bin/python" ]]; then
  VENV_DIR="${BACKEND_DIR}/venv"
fi

cd "$BACKEND_DIR"

if ! command -v pm2 >/dev/null 2>&1; then
  export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
  if [[ -s "$NVM_DIR/nvm.sh" ]]; then
    # PM2 is commonly installed under the deployment user's NVM environment.
    # shellcheck source=/dev/null
    source "$NVM_DIR/nvm.sh"
  fi
fi

command -v pm2 >/dev/null 2>&1 || {
  echo "PM2 is not available for user $(id -un)."
  exit 1
}

test -f .env || {
  echo "Backend .env is missing at ${BACKEND_DIR}/.env"
  exit 1
}

if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
  python3.11 -m venv "$VENV_DIR"
fi

"${VENV_DIR}/bin/python" -m pip install \
  --disable-pip-version-check \
  --no-cache-dir \
  -r requirements.txt

"${VENV_DIR}/bin/python" -m py_compile \
  main.py \
  rag_engine.py \
  claude_client.py \
  document_processor.py \
  pipeline_progress.py

if pm2 describe "$PM2_APP_NAME" >/dev/null 2>&1; then
  pm2 restart "$PM2_APP_NAME" --update-env
else
  pm2 start "${VENV_DIR}/bin/uvicorn" \
    --name "$PM2_APP_NAME" \
    --cwd "$BACKEND_DIR" \
    -- main:app --host 127.0.0.1 --port 8000
fi

pm2 save

for attempt in {1..20}; do
  if curl --fail --silent http://127.0.0.1:8000/health >/dev/null; then
    echo "Backend deployment is healthy."
    exit 0
  fi
  sleep 3
done

echo "Backend health check failed."
pm2 logs "$PM2_APP_NAME" --lines 80 --nostream || true
exit 1
