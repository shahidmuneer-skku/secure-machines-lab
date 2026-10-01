#!/usr/bin/env bash
# Runs the whole stack for development; Ctrl+C stops everything.
# If you reach localhost:3000 through an SSH tunnel, also forward 8100 (long-form streaming)
# and 58333 (media storage).
# Infrastructure (Postgres, Redis, RabbitMQ, S3) must be up:
#   docker compose -f deploy/compose/docker-compose.yml --env-file .env up -d
#
#   scripts/dev.sh              # API, background worker + beat, model workers (GPUs 0 and 3), web
#   GPUS=0 scripts/dev.sh       # model workers on other GPUs (comma-separated; GPU=2 still works)
#   NO_MODELS=1 scripts/dev.sh  # skip the model worker
#   NO_STREAM=1 scripts/dev.sh  # skip the long-form stream service
#   NO_RESIDENT=1 scripts/dev.sh  # do not keep models loaded (each task loads its model; no image studio)
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
LOGS="$ROOT/var/log"
mkdir -p "$LOGS"
pids=()

start() {  # start <name> <dir> <command...>
  local name=$1 dir=$2; shift 2
  (cd "$dir" && exec "$@") >"$LOGS/$name.log" 2>&1 &
  pids+=($!)
  echo "started $name (pid $!, log var/log/$name.log)"
}

cleanup() {
  echo "stopping..."
  kill "${pids[@]}" 2>/dev/null || true
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

export DJANGO_SETTINGS_MODULE=sml.settings.dev
# Apply pending migrations first: the API would otherwise answer 500 to anything touching a new column.
# bootstrap is idempotent: it adds new roles' capabilities and new price rules without touching edits.
(cd "$ROOT/apps/api" && uv run python manage.py migrate --noinput && uv run python manage.py bootstrap)
start api "$ROOT/apps/api" uv run uvicorn sml.asgi:application --host 127.0.0.1 --port 8000 --reload --reload-dir sml \
  --timeout-graceful-shutdown 5  # live-update (SSE) streams would otherwise block every reload
start celery-api "$ROOT/apps/api" uv run celery -A sml worker -B -n api@%h --concurrency 4 --loglevel INFO \
  -Q sml.default,sml.results,sml.reports,sml.maintenance
if [[ -z "${NO_MODELS:-}" ]]; then
  # One detector worker per GPU; they share the queues and each admits work by its own GPU's memory.
  IFS=',' read -ra gpus <<< "${GPUS:-${GPU:-0,3}}"
  for gpu in "${gpus[@]}"; do
    start "worker-gpu$gpu" "$ROOT/apps/worker" uv run python -m sml_worker --detectors --gpu "$gpu" --concurrency 4
  done
  start agents "$ROOT/apps/worker" uv run python -m sml_worker --agents --concurrency "${SML_AGENT_PARALLEL:-2}"
  # Image studio jobs; they run on the studio server, which the resident supervisor below starts.
  start studio "$ROOT/apps/worker" uv run python -m sml_worker --studio --concurrency 2
  # Keeps the models with a `resident` block loaded on their GPUs (NO_RESIDENT=1 to load per task),
  # and the image studio's server (config/studio.yaml) with the admin's models.
  if [[ -z "${NO_RESIDENT:-}" ]]; then
    start resident "$ROOT/apps/worker" uv run python -m sml_worker --resident
  fi
fi
if [[ -z "${NO_STREAM:-}" ]]; then
  # Long-form stream service: the legacy conda env (torch + engine), on its own GPU.
  set -a; . "$ROOT/.env"; set +a
  STREAM_PY="${CONDA_ROOT:-$HOME/anaconda3}/envs/${STREAM_CONDA_ENV:-safe}/bin/python"
  CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES="${SML_STREAM_GPU:-2}" PYTHONPATH="$ROOT/apps/stream" \
    start stream "$ROOT/apps/stream" "$STREAM_PY" -m uvicorn sml_stream.app:app --host 127.0.0.1 --port 8100
fi
start web "$ROOT/apps/web" npx next dev -p 3000

echo "web http://localhost:3000 · API docs http://localhost:3000/api/docs · Ctrl+C to stop"
wait -n
echo "a process exited; see var/log/"
