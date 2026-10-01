"""Keeps the studio server told which models the admin picked (also after a Redis restart)."""

from __future__ import annotations

from celery import shared_task


@shared_task(name="sml.maintenance.studio_keep", ignore_result=True)
def studio_keep() -> None:
    from .services import sync_keep

    sync_keep()
