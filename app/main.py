import logging
from pathlib import Path
from typing import Optional

from fastapi import BackgroundTasks, Depends, FastAPI, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.config import settings
from app.database import Base, SessionLocal, engine, get_db
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
    platform: Optional[str] = None,
    category: Optional[str] = None,
    q: Optional[str] = None,
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


def _background_refresh() -> None:
    db = SessionLocal()
    try:
        refresh_news(db)
    finally:
        db.close()


@app.post("/api/refresh")
def api_refresh(background_tasks: BackgroundTasks) -> dict:
    background_tasks.add_task(_background_refresh)
    return {"status": "started", "message": "新闻抓取已在后台开始"}
