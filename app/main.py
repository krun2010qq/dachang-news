from __future__ import annotations

import logging
from pathlib import Path

from fastapi import Depends, FastAPI, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.config import settings
from app.database import Base, engine, get_db
from app.news_service import get_stats, list_news, refresh_news
from app.scheduler import start_scheduler, stop_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(title=settings.app_name)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    start_scheduler()
    db = next(get_db())
    try:
        stats = get_stats(db)
        if stats["total"] == 0:
            logger.info("Empty database, running initial news fetch...")
            refresh_news(db)
    finally:
        db.close()


@app.on_event("shutdown")
def on_shutdown() -> None:
    stop_scheduler()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "app": settings.app_name}


@app.get("/api/news")
def api_news(
    platform: str | None = None,
    category: str | None = None,
    q: str | None = None,
    limit: int = Query(default=80, le=200),
    db: Session = Depends(get_db),
) -> dict:
    items = list_news(db, platform=platform, category=category, q=q, limit=limit)
    return {
        "items": [
            {
                "id": item.id,
                "title": item.title,
                "summary": item.summary,
                "url": item.url,
                "source": item.source,
                "platform": item.platform,
                "category": item.category,
                "published_at": item.published_at,
                "fetched_at": item.fetched_at.isoformat() if item.fetched_at else "",
            }
            for item in items
        ]
    }


@app.get("/api/stats")
def api_stats(db: Session = Depends(get_db)) -> dict:
    return get_stats(db)


@app.post("/api/refresh")
def api_refresh(db: Session = Depends(get_db)) -> dict:
    return refresh_news(db)
