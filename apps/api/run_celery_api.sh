#!/usr/bin/env bash
# (Re)starts the API's Celery worker + beat (dispatcher, results, reports, maintenance).
# Any running copy is stopped first, so it never runs twice. Log: var/log/celery-api.log
#   apps/api/run_celery_api.sh            # (re)start
#   apps/api/run_celery_api.sh --stop     # stop only
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
LOGS="$HERE/../../var/log"
mkdir -p "$LOGS"
PATTERN="celery -A sml worker -B -n api@"
STOP_TIMEOUT=${STOP_TIMEOUT:-60}

stop() {  # stop <pattern>: SIGTERM (warm shutdown), then SIGKILL after STOP_TIMEOUT seconds
  local pattern=$1
  pgrep -f -- "$pattern" >/dev/null || return 0
  echo "stopping: $pattern"
  pkill -TERM -f -- "$pattern" || true
  for _ in $(seq "$STOP_TIMEOUT"); do
    pgrep -f -- "$pattern" >/dev/null || return 0
    sleep 1
  done
  echo "  still running after ${STOP_TIMEOUT}s; killing"
  pkill -KILL -f -- "$pattern" || true
  sleep 1
}

stop "$PATTERN"
# Pool processes left behind by an earlier crash (their parent is gone).
stop "$HERE/.venv/bin/celery -A sml worker"
if [[ "${1:-}" == "--stop" ]]; then exit 0; fi

cd "$HERE"
DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE:-sml.settings.dev} setsid -f nohup uv run celery -A sml worker -B \
  -n api@%h --concurrency 4 --loglevel INFO -Q sml.default,sml.results,sml.reports,sml.maintenance \
  >> "$LOGS/celery-api.log" 2>&1 < /dev/null
echo "started celery-api (log var/log/celery-api.log)"
