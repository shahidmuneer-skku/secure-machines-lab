#!/usr/bin/env bash
# Builds and activates the checked-out revision on a production host.
#   deploy/release.sh             # after `git pull`
# Order: dependencies → database migrations → static files → web build → restart.
# Migrations must stay backwards compatible with the previous release (expand/contract),
# because API processes are restarted after the database is migrated.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
export DJANGO_SETTINGS_MODULE=sml.settings.prod

step() { printf '\n==> %s\n' "$*"; }

step "API dependencies"
cd "$ROOT/apps/api" && uv sync --frozen --no-dev
manage() { (cd "$ROOT/apps/api" && set -a && . "$ROOT/.env" && set +a && .venv/bin/python manage.py "$@"); }

step "System checks"
manage check --deploy --fail-level WARNING

step "Database migrations"
manage migrate --noinput

step "Static files, RBAC, prices and broker policy"
manage collectstatic --noinput
manage bootstrap
manage setup_broker

step "Model worker dependencies"
cd "$ROOT/apps/worker" && uv sync --frozen --no-dev

step "Web build"
cd "$ROOT/apps/web" && npm ci && npx next build

step "Restart"
sudo systemctl restart sml-api.service sml-celery.service sml-beat.service sml-web.service
# Model workers finish their current detections first (warm shutdown, up to 10 minutes).
sudo systemctl restart 'sml-worker@*.service'

step "Readiness"
for _ in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8000/api/readyz >/dev/null; then echo "API ready"; exit 0; fi
  sleep 2
done
echo "API did not become ready; check: journalctl -u sml-api -n 100" >&2
exit 1
