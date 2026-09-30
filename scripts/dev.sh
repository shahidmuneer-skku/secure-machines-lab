#!/usr/bin/env bash
# Runs the whole stack for development; Ctrl+C stops everything.
# Infrastructure (Postgres, Redis, RabbitMQ, S3) must be up:
#   docker compose -f deploy/compose/docker-compose.yml --env-file .env up -d
#
#   scripts/dev.sh              # API, background worker + beat, model worker (GPU 0), web
#   GPU=2 scripts/dev.sh        # model worker on another GPU
#   NO_MODELS=1 scripts/dev.sh  # skip the model worker
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
start api "$ROOT/apps/api" uv run uvicorn sml.asgi:application --host 127.0.0.1 --port 8000 --reload --reload-dir sml
start celery-api "$ROOT/apps/api" uv run celery -A sml worker -B -n api@%h --concurrency 4 --loglevel INFO \
  -Q sml.default,sml.results,sml.reports,sml.maintenance
if [[ -z "${NO_MODELS:-}" ]]; then
  start worker "$ROOT/apps/worker" uv run python -m sml_worker --all --gpu "${GPU:-0}" --concurrency 2
fi
start web "$ROOT/apps/web" npx next dev -p 3000

echo "web http://localhost:3000 · API docs http://localhost:3000/api/docs · Ctrl+C to stop"
wait -n
echo "a process exited; see var/log/"
