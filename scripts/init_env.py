#!/usr/bin/env python3
"""Create .env from .env.example with random secrets and matching connection URLs.

    python3 scripts/init_env.py                                   # development
    python3 scripts/init_env.py --production \\
        --app-domain app.example.com --media-domain media.example.com

Refuses to overwrite an existing file (use --force; the old file is kept as .env.bak).
Also writes the web app's env file (apps/web/.env.local, or .env.production.local).
"""

from __future__ import annotations

import argparse
import os
import secrets
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def render(template: str, values: dict[str, str]) -> str:
    out = []
    for line in template.splitlines():
        key, sep, _ = line.partition("=")
        if sep and not line.startswith("#") and key in values:
            value = values[key]
            line = f'{key}="{value}"' if " " in value else f"{key}={value}"
        out.append(line)
    return "\n".join(out) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--production", action="store_true")
    parser.add_argument("--app-domain", help="e.g. app.example.com (required with --production)")
    parser.add_argument("--media-domain", help="e.g. media.example.com (required with --production)")
    parser.add_argument("--output", type=Path, default=ROOT / ".env")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if args.production and not (args.app_domain and args.media_domain):
        parser.error("--production needs --app-domain and --media-domain")
    if args.output.exists() and not args.force:
        print(f"{args.output} already exists; use --force to replace it (a backup is kept).", file=sys.stderr)
        return 1

    pw = {name: secrets.token_hex(24) for name in ("POSTGRES", "REDIS", "RABBITMQ")}
    values = {
        "DJANGO_SECRET_KEY": secrets.token_urlsafe(64),
        "API_KEY_PEPPER": secrets.token_urlsafe(32),
        "FIELD_ENCRYPTION_KEY": secrets.token_urlsafe(32),
        "POSTGRES_PASSWORD": pw["POSTGRES"],
        "DATABASE_URL": f"postgres://sml:{pw['POSTGRES']}@127.0.0.1:55432/sml",
        "REDIS_PASSWORD": pw["REDIS"],
        "REDIS_URL": f"redis://:{pw['REDIS']}@127.0.0.1:56379/0",
        "RABBITMQ_PASSWORD": pw["RABBITMQ"],
        "RABBITMQ_MANAGEMENT_PASSWORD": pw["RABBITMQ"],
        "CELERY_BROKER_URL": f"amqp://sml:{pw['RABBITMQ']}@127.0.0.1:55672/sml",
        "S3_ACCESS_KEY": "sml" + secrets.token_hex(6),
        "S3_SECRET_KEY": secrets.token_urlsafe(32),
        "STREAM_SHARED_SECRET": secrets.token_urlsafe(32),
    }
    storage_origin = "http://127.0.0.1:58333"
    if args.production:
        app, media = f"https://{args.app_domain}", f"https://{args.media_domain}"
        storage_origin = media
        values |= {
            "DJANGO_ENV": "production", "DJANGO_SETTINGS_MODULE": "sml.settings.prod", "DJANGO_DEBUG": "false",
            "DJANGO_ALLOWED_HOSTS": args.app_domain, "PUBLIC_WEB_URL": app, "CSRF_TRUSTED_ORIGINS": app,
            "S3_PUBLIC_ENDPOINT_URL": media, "API_KEY_ENV_LABEL": "live", "STREAM_PUBLIC_URL": "/stream/ws",
            "EMAIL_BACKEND": "django.core.mail.backends.smtp.EmailBackend",
        }

    template = (ROOT / ".env.example").read_text()
    if args.output.exists():
        shutil.copy2(args.output, args.output.with_name(args.output.name + ".bak"))
    args.output.write_text(render(template, values))
    os.chmod(args.output, 0o600)
    print(f"wrote {args.output} (mode 600)")

    web_env = ROOT / "apps" / "web" / (".env.production.local" if args.production else ".env.local")
    if args.output == ROOT / ".env" and not web_env.exists():
        stream_origin = "" if args.production else "ws://localhost:8100"
        web_env.write_text(f"API_ORIGIN=http://127.0.0.1:8000\nSTORAGE_ORIGIN={storage_origin}\n"
                           f"STREAM_ORIGIN={stream_origin}\n")
        os.chmod(web_env, 0o600)
        print(f"wrote {web_env}")

    todo = ["SUPERADMIN_EMAIL / SUPERADMIN_PASSWORD"]
    if args.production:
        todo += ["SMTP (EMAIL_HOST, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD)", "TOSS_* and STRIPE_* live keys",
                 "TURNSTILE_* keys"]
    print("Still to fill in by hand: " + "; ".join(todo))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
