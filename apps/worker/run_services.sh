#!/usr/bin/env bash
# (Re)starts the background services: the API's Celery worker, the detector workers, the agents,
# the resident model servers + image studio server, and the studio worker.
# Every service is stopped first if it is already running, so none ever runs twice.
#
#   apps/worker/run_services.sh               # everything (detector workers on GPUs 0 and 3)
#   GPUS="0" apps/worker/run_services.sh      # detector workers on other GPUs
#   apps/worker/run_services.sh stop          # stop everything, start nothing
#
# Logs: var/log/{celery-api,worker-gpu<N>,agents,resident,resident-<server>,studio}.log
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../.." && pwd)
LOGS="$ROOT/var/log"
mkdir -p "$LOGS"
STOP_TIMEOUT=${STOP_TIMEOUT:-60}
GPUS=${GPUS:-"0 3"}

stop() {  # stop <pattern>: SIGTERM (finish or requeue the current task), then SIGKILL after STOP_TIMEOUT s
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

start() {  # start <name> <args...>: a detached worker process logging to var/log/<name>.log
  local name=$1; shift
  (cd "$HERE" && setsid -f nohup .venv/bin/python -m sml_worker "$@" >> "$LOGS/$name.log" 2>&1 < /dev/null)
  echo "started $name (log var/log/$name.log)"
}

stop "sml_worker --detectors"
stop "sml_worker --agents"
stop "sml_worker --studio"
# The supervisor stops its model servers; any left behind (a killed supervisor) are stopped too, so
# no model stays loaded twice on a GPU.
stop "sml_worker --resident"
stop "sml_worker/resident/server.py --config"
stop "sml_worker/studio/server.py --config"

if [[ "${1:-}" == "stop" ]]; then
  STOP_TIMEOUT=$STOP_TIMEOUT "$ROOT/apps/api/run_celery_api.sh" --stop
  echo "stopped"
  exit 0
fi

STOP_TIMEOUT=$STOP_TIMEOUT "$ROOT/apps/api/run_celery_api.sh"
for gpu in $GPUS; do
  start "worker-gpu$gpu" --detectors --gpu "$gpu" --concurrency 4
done
start agents --agents --concurrency "${SML_AGENT_PARALLEL:-2}"
start resident --resident
start studio --studio --concurrency 2
echo "done. Workers appear in Admin → Queues & workers within a minute; resident models and the studio"
echo "model need 1-2 minutes more (var/log/resident.log shows 'ready after')."
