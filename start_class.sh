#!/usr/bin/env bash
# Start JupyterLab for AI Agents for Beginners course.
# - Root dir: this repo
# - Kernel: conda env gemma4
# - Opens browser to the course tree
#
# Usage:
#   bash start_class.sh
#   bash start_class.sh --port 8889
#   bash start_class.sh --no-browser

set -euo pipefail

COURSE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GEMMA4_ENV="${GEMMA4_ENV:-/home/wanghao/desktop/envs/miniconda3/envs/gemma4}"
PYTHON="${GEMMA4_ENV}/bin/python"
JUPYTER="${GEMMA4_ENV}/bin/jupyter"

PORT="${JUPYTER_PORT:-8888}"
IP="${JUPYTER_IP:-127.0.0.1}"
OPEN_BROWSER=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port)
      PORT="$2"
      shift 2
      ;;
    --ip)
      IP="$2"
      shift 2
      ;;
    --no-browser)
      OPEN_BROWSER=0
      shift
      ;;
    -h|--help)
      sed -n '2,12p' "$0" | sed 's/^# \?//'
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
done

if [[ ! -x "$PYTHON" ]]; then
  echo "ERROR: gemma4 python not found: $PYTHON" >&2
  exit 1
fi
if [[ ! -x "$JUPYTER" ]]; then
  echo "ERROR: jupyter not found in gemma4 env: $JUPYTER" >&2
  echo "  Install with: $PYTHON -m pip install jupyterlab ipykernel" >&2
  exit 1
fi

# Ensure gemma4 is registered as a selectable kernel
"$PYTHON" -m ipykernel install --user --name=gemma4 --display-name="Python (gemma4)" >/dev/null

# Prefer a free port if default is busy
if command -v ss >/dev/null 2>&1; then
  if ss -lnt 2>/dev/null | grep -q ":${PORT} "; then
    for try in $(seq "$PORT" $((PORT + 20))); do
      if ! ss -lnt 2>/dev/null | grep -q ":${try} "; then
        PORT=$try
        break
      fi
    done
  fi
fi

URL="http://${IP}:${PORT}/lab/tree/README.md"

echo "=============================================="
echo " AI Agents for Beginners"
echo " course : $COURSE_ROOT"
echo " kernel : Python (gemma4)"
echo "          $GEMMA4_ENV"
echo " url    : $URL"
echo "=============================================="
echo
echo "In notebooks: Kernel → Change Kernel → Python (gemma4)"
echo "Stop with Ctrl+C"
echo

# Open browser shortly after lab starts (default jupyter may also open; this targets course README)
if [[ "$OPEN_BROWSER" -eq 1 ]]; then
  (
    for _ in $(seq 1 60); do
      if curl -sf -o /dev/null "http://${IP}:${PORT}/lab" 2>/dev/null \
        || curl -sf -o /dev/null "http://127.0.0.1:${PORT}/lab" 2>/dev/null; then
        if command -v xdg-open >/dev/null 2>&1; then
          xdg-open "$URL" >/dev/null 2>&1 || true
        elif command -v sensible-browser >/dev/null 2>&1; then
          sensible-browser "$URL" >/dev/null 2>&1 || true
        fi
        break
      fi
      sleep 0.5
    done
  ) &
fi

cd "$COURSE_ROOT"
# Run jupyter from gemma4 so default runtime matches that env
exec "$JUPYTER" lab \
  --notebook-dir="$COURSE_ROOT" \
  --ip="$IP" \
  --port="$PORT" \
  --no-browser \
  --ServerApp.token='' \
  --ServerApp.password='' \
  --ServerApp.open_browser=False \
  --LabApp.default_url="/lab/tree/README.md"
