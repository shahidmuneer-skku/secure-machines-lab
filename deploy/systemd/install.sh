#!/usr/bin/env bash
# Renders the unit templates for this checkout and installs them.
#
#   sudo GPUS="0 3" deploy/systemd/install.sh       # install + enable (one model worker per GPU;
#                                                   # GPU 2 is the long-form stream service's, see SML_STREAM_GPU)
#   DESTDIR=/tmp/units deploy/systemd/install.sh    # only render, for review
#
# SERVICE_USER defaults to the user who invoked sudo; NODE_BIN to that user's `node`.
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../.." && pwd)
SERVICE_USER=${SERVICE_USER:-${SUDO_USER:-$(id -un)}}
SERVICE_GROUP=${SERVICE_GROUP:-$(id -gn "$SERVICE_USER")}
NODE_BIN=${NODE_BIN:-$(sudo -u "$SERVICE_USER" -i bash -c 'command -v node' 2>/dev/null || command -v node)}
GPUS=${GPUS:-0}
DEST=${DESTDIR:-/etc/systemd/system}

[[ -x "$NODE_BIN" ]] || { echo "node not found; set NODE_BIN=/path/to/node" >&2; exit 1; }
[[ -f "$ROOT/.env" ]] || { echo "missing $ROOT/.env (copy .env.example and fill it in)" >&2; exit 1; }
if [[ -z "${DESTDIR:-}" && $EUID -ne 0 ]]; then
  echo "run with sudo (or set DESTDIR to only render the units)" >&2; exit 1
fi

mkdir -p "$DEST" "$ROOT/var" "$ROOT/apps/web/.next/cache"
chown "$SERVICE_USER:$SERVICE_GROUP" "$ROOT/var" "$ROOT/apps/web/.next/cache" 2>/dev/null || true

for template in "$HERE"/*.service.in; do
  unit=$(basename "${template%.in}")
  sed -e "s|@ROOT@|$ROOT|g" -e "s|@USER@|$SERVICE_USER|g" -e "s|@GROUP@|$SERVICE_GROUP|g" \
      -e "s|@NODE@|$NODE_BIN|g" -e "s|@HOME@|$(getent passwd "$SERVICE_USER" | cut -d: -f6)|g" \
      "$template" > "$DEST/$unit"
  echo "rendered $DEST/$unit"
done
install -m 0644 "$HERE/sml.target" "$DEST/sml.target"

if [[ -n "${DESTDIR:-}" ]]; then
  echo "Rendered only (DESTDIR set); nothing was enabled."
  exit 0
fi

systemctl daemon-reload
workers=()
for gpu in $GPUS; do workers+=("sml-worker@$gpu.service"); done
systemctl enable sml.target sml-api.service sml-celery.service sml-beat.service sml-web.service sml-stream.service \
  sml-resident.service \
  sml-agents.service \
  "${workers[@]}"
echo "Installed. Start everything with: sudo systemctl start sml.target ${workers[*]}"
