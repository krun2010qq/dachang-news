from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.database import SessionLocal
from app.news_service import refresh_news

logger = logging.getLogger(__name__)
_scheduler: BackgroundScheduler | None = None


def _run_refresh() -> None:
    db = SessionLocal()
    try:
        result = refresh_news(db)
        logger.info("Scheduled refresh: %s", result)
    finally:
        db.close()


def start_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler and _scheduler.running:
        return _scheduler

    morning_h, morning_m = settings.scheduler_morning.split(":")
    afternoon_h, afternoon_m = settings.scheduler_afternoon.split(":")

    scheduler = BackgroundScheduler(timezone=settings.timezone)
    scheduler.add_job(
        _run_refresh,
        CronTrigger(hour=int(morning_h), minute=int(morning_m)),
        id="morning_refresh",
        replace_existing=True,
    )
    scheduler.add_job(
        _run_refresh,
        CronTrigger(hour=int(afternoon_h), minute=int(afternoon_m)),
        id="afternoon_refresh",
        replace_existing=True,
    )
    scheduler.start()
    _scheduler = scheduler
    return scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
    _scheduler = None
