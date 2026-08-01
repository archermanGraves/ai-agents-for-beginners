#!/usr/bin/env bash
# Start AI Agents for Beginners class stack:
#   1) local vLLM on :8030 (tool-calling enabled) — auto if not already healthy
#   2) ensure .env LOCAL_VLLM_* / OPENAI_* points at that endpoint
#   3) register Jupyter kernels (agent_run preferred, gemma4 fallback)
#   4) launch JupyterLab at course root
#
# Usage:
#   bash start_class.sh
#   bash start_class.sh --port 8889
#   bash start_class.sh --no-browser
#   bash start_class.sh --skip-vllm          # only Jupyter (reuse existing vLLM)
#   bash start_class.sh --keep-vllm          # do not stop vLLM we started on exit
#   GPU_MEMORY_UTILIZATION=0.30 bash start_class.sh

set -euo pipefail

COURSE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_RUN_ENV="${AGENT_RUN_ENV:-/home/wanghao/desktop/envs/miniconda3/envs/agent_run}"
GEMMA4_ENV="${GEMMA4_ENV:-/home/wanghao/desktop/envs/miniconda3/envs/gemma4}"
VLLM_SCRIPT="${COURSE_ROOT}/start_vllm_for_agents.sh"
VLLM_BASE_URL="${LOCAL_VLLM_BASE_URL:-http://127.0.0.1:8030/v1}"
VLLM_PORT="${VLLM_PORT:-8030}"
VLLM_LOG="${COURSE_ROOT}/.vllm_agents.log"
VLLM_PID_FILE="${COURSE_ROOT}/.vllm_agents.pid"

PORT="${JUPYTER_PORT:-8888}"
IP="${JUPYTER_IP:-127.0.0.1}"
OPEN_BROWSER=1
SKIP_VLLM=0
KEEP_VLLM=0
STARTED_VLLM=0
VLLM_PID=""

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
    --skip-vllm)
      SKIP_VLLM=1
      shift
      ;;
    --keep-vllm)
      KEEP_VLLM=1
      shift
      ;;
    -h|--help)
      sed -n '2,16p' "$0" | sed 's/^# \?//'
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
done

# Prefer agent_run (local_api notebooks / MAF), fall back to gemma4 for Jupyter itself.
if [[ -x "${AGENT_RUN_ENV}/bin/jupyter" ]]; then
  JUPYTER_ENV="$AGENT_RUN_ENV"
elif [[ -x "${GEMMA4_ENV}/bin/jupyter" ]]; then
  JUPYTER_ENV="$GEMMA4_ENV"
else
  echo "ERROR: neither agent_run nor gemma4 has jupyterlab installed." >&2
  echo "  Tried: ${AGENT_RUN_ENV}/bin/jupyter" >&2
  echo "         ${GEMMA4_ENV}/bin/jupyter" >&2
  exit 1
fi
PYTHON="${JUPYTER_ENV}/bin/python"
JUPYTER="${JUPYTER_ENV}/bin/jupyter"

vllm_healthy() {
  curl --noproxy '*' -sf --max-time 3 "${VLLM_BASE_URL}/models" >/dev/null 2>&1
}

ensure_local_env() {
  local env_file="${COURSE_ROOT}/.env"
  local example="${COURSE_ROOT}/.env.example"
  if [[ ! -f "$env_file" && -f "$example" ]]; then
    cp "$example" "$env_file"
    echo "[env] created .env from .env.example"
  fi
  touch "$env_file"

  _upsert_env() {
    local key="$1" value="$2"
    if grep -qE "^${key}=" "$env_file" 2>/dev/null; then
      # Keep existing value; only fill empty/placeholder lines for local keys
      local cur
      cur="$(grep -E "^${key}=" "$env_file" | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'")"
      if [[ -z "$cur" || "$cur" == "..." ]]; then
        sed -i "s|^${key}=.*|${key}=${value}|" "$env_file"
      fi
    else
      printf '\n%s=%s\n' "$key" "$value" >>"$env_file"
    fi
  }

  _upsert_env "LOCAL_VLLM_BASE_URL" "http://127.0.0.1:${VLLM_PORT}/v1"
  _upsert_env "LOCAL_VLLM_API_KEY" "EMPTY"
  _upsert_env "OPENAI_BASE_URL" "http://127.0.0.1:${VLLM_PORT}/v1"
  _upsert_env "OPENAI_API_KEY" "EMPTY"

  # Runtime env for this shell / jupyter child
  export LOCAL_VLLM_BASE_URL="http://127.0.0.1:${VLLM_PORT}/v1"
  export LOCAL_VLLM_API_KEY="${LOCAL_VLLM_API_KEY:-EMPTY}"
  export OPENAI_BASE_URL="http://127.0.0.1:${VLLM_PORT}/v1"
  export OPENAI_API_KEY="${OPENAI_API_KEY:-EMPTY}"
  export NO_PROXY="127.0.0.1,localhost,${NO_PROXY:-}"
  export no_proxy="127.0.0.1,localhost,${no_proxy:-}"
  unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY all_proxy || true

  echo "[env] LOCAL_VLLM_BASE_URL=${LOCAL_VLLM_BASE_URL}"
}

start_vllm_if_needed() {
  if [[ "$SKIP_VLLM" -eq 1 ]]; then
    echo "[vllm] skipped (--skip-vllm)"
    return 0
  fi
  if [[ ! -x "$VLLM_SCRIPT" && ! -f "$VLLM_SCRIPT" ]]; then
    echo "ERROR: missing ${VLLM_SCRIPT}" >&2
    exit 1
  fi
  chmod +x "$VLLM_SCRIPT" 2>/dev/null || true

  if vllm_healthy; then
    echo "[vllm] already healthy at ${VLLM_BASE_URL}"
    return 0
  fi

  # Port occupied but unhealthy → refuse to fight another process
  if command -v ss >/dev/null 2>&1 && ss -lnt 2>/dev/null | grep -q ":${VLLM_PORT} "; then
    echo "ERROR: port ${VLLM_PORT} is in use but ${VLLM_BASE_URL}/models is not healthy." >&2
    echo "  Free the port or fix the existing server, then retry." >&2
    exit 1
  fi

  echo "[vllm] starting (tool-calling) via start_vllm_for_agents.sh ..."
  echo "[vllm] log → ${VLLM_LOG}"
  # Lower default VRAM so class + other GPU jobs can coexist; override with env.
  export GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.30}"
  export PORT="${VLLM_PORT}"
  nohup bash "$VLLM_SCRIPT" >"$VLLM_LOG" 2>&1 &
  VLLM_PID=$!
  echo "$VLLM_PID" >"$VLLM_PID_FILE"
  STARTED_VLLM=1
  echo "[vllm] pid=${VLLM_PID}"

  local i
  for i in $(seq 1 180); do
    if ! kill -0 "$VLLM_PID" 2>/dev/null; then
      echo "ERROR: vLLM exited early. Tail of log:" >&2
      tail -n 40 "$VLLM_LOG" >&2 || true
      exit 1
    fi
    if vllm_healthy; then
      local model
      model="$(curl --noproxy '*' -sS --max-time 5 "${VLLM_BASE_URL}/models" \
        | "${PYTHON}" -c "import sys,json; d=json.load(sys.stdin); print(d['data'][0]['id'] if d.get('data') else '')" 2>/dev/null || true)"
      echo "[vllm] ready · model=${model:-unknown}"
      return 0
    fi
    sleep 2
    if (( i % 15 == 0 )); then
      echo "[vllm] still loading... (${i}s+)"
    fi
  done

  echo "ERROR: timed out waiting for vLLM at ${VLLM_BASE_URL}" >&2
  tail -n 40 "$VLLM_LOG" >&2 || true
  exit 1
}

stop_vllm_if_started() {
  if [[ "$STARTED_VLLM" -ne 1 || "$KEEP_VLLM" -eq 1 ]]; then
    return 0
  fi
  local pid="${VLLM_PID:-}"
  if [[ -z "$pid" && -f "$VLLM_PID_FILE" ]]; then
    pid="$(cat "$VLLM_PID_FILE" 2>/dev/null || true)"
  fi
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    echo
    echo "[vllm] stopping pid=${pid} (started by this script) ..."
    kill -TERM "$pid" 2>/dev/null || true
    for _ in $(seq 1 20); do
      kill -0 "$pid" 2>/dev/null || break
      sleep 0.5
    done
    kill -KILL "$pid" 2>/dev/null || true
    # Also stop child vllm serve if still holding the port
    if command -v pkill >/dev/null 2>&1; then
      pkill -f "vllm serve .*--port ${VLLM_PORT}" 2>/dev/null || true
    fi
  fi
  rm -f "$VLLM_PID_FILE"
}

register_kernels() {
  if [[ -x "${AGENT_RUN_ENV}/bin/python" ]]; then
    "${AGENT_RUN_ENV}/bin/python" -m ipykernel install --user \
      --name=agent_run --display-name="Python (agent_run)" >/dev/null 2>&1 || true
    echo "[kernel] Python (agent_run) registered"
  fi
  if [[ -x "${GEMMA4_ENV}/bin/python" ]]; then
    "${GEMMA4_ENV}/bin/python" -m ipykernel install --user \
      --name=gemma4 --display-name="Python (gemma4)" >/dev/null 2>&1 || true
    echo "[kernel] Python (gemma4) registered"
  fi
}

pick_free_jupyter_port() {
  if command -v ss >/dev/null 2>&1; then
    if ss -lnt 2>/dev/null | grep -q ":${PORT} "; then
      local try
      for try in $(seq "$PORT" $((PORT + 20))); do
        if ! ss -lnt 2>/dev/null | grep -q ":${try} "; then
          PORT=$try
          break
        fi
      done
    fi
  fi
}

trap 'stop_vllm_if_started' EXIT INT TERM

ensure_local_env
start_vllm_if_needed
register_kernels
pick_free_jupyter_port

URL="http://${IP}:${PORT}/lab/tree/README.md"

echo "=============================================="
echo " AI Agents for Beginners (local API)"
echo " course : $COURSE_ROOT"
echo " vLLM   : ${VLLM_BASE_URL}  (tool-calling)"
echo " jupyter: $JUPYTER_ENV"
echo " kernel : prefer Python (agent_run)"
echo " url    : $URL"
echo "=============================================="
echo
echo "In notebooks: Kernel → Change Kernel → Python (agent_run)"
echo "Stop with Ctrl+C  (also stops vLLM started by this script unless --keep-vllm)"
echo

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
# Do not use exec: need EXIT trap to stop vLLM we started.
"$JUPYTER" lab \
  --notebook-dir="$COURSE_ROOT" \
  --ip="$IP" \
  --port="$PORT" \
  --no-browser \
  --ServerApp.token='' \
  --ServerApp.password='' \
  --ServerApp.open_browser=False \
  --LabApp.default_url="/lab/tree/README.md"

: <<'CLI_EOF'
"""
# one-shot class launch (auto vLLM + JupyterLab)
bash /home/wanghao/desktop/ai-vision-workbench/class_demo/ai-agents-for-beginners/start_class.sh
# keep vLLM after Ctrl+C:
# bash start_class.sh --keep-vllm
# Jupyter only (reuse already-running :8030):
# bash start_class.sh --skip-vllm
"""
CLI_EOF
