"""
booking/scheduler.py  –  APScheduler-Integration für den Spielplan-Sync-Cron-Job

Wird von web/main.py (lifespan) und web/routers/admin.py (Konfigurationsroute)
verwendet.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from fastapi import FastAPI


async def _run_spielplan_sync(app: "FastAPI") -> None:
    """Führt den Spielplan-Sync aus (Callback für den Cron-Job)."""
    try:
        from booking.spielplan_sync import sync_spielplan, write_sync_status
        result = await sync_spielplan(app.state.repo, app.state.settings)
        write_sync_status(result, "cron")
    except Exception as exc:
        from booking.spielplan_sync import SyncResult, write_sync_status
        write_sync_status(SyncResult(fehler=[str(exc)]), "cron")


def apply_schedule(scheduler: "AsyncIOScheduler", app: "FastAPI") -> None:
    """
    Liest die Scheduler-Felder aus vereinsconfig.json und passt den APScheduler-Job an.
    Wird beim Start und nach jeder Konfigurationsänderung aufgerufen.
    """
    from apscheduler.triggers.cron import CronTrigger
    from booking.scheduler_config import load

    cfg = load()

    if scheduler.get_job("spielplan_sync"):
        scheduler.remove_job("spielplan_sync")

    if cfg.spielplan_sync_enabled:
        try:
            h, m = cfg.spielplan_sync_uhrzeit.split(":")
            scheduler.add_job(
                _run_spielplan_sync,
                CronTrigger(hour=int(h), minute=int(m)),
                id="spielplan_sync",
                kwargs={"app": app},
            )
        except Exception:
            pass
