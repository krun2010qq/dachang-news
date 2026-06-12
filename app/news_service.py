from datetime import datetime
from typing import List, Optional

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.models import FetchLog, NewsItem
from app.news_fetcher import fetch_all_news


def refresh_news(db: Session) -> dict:
    log = FetchLog(status="running", started_at=datetime.utcnow())
    db.add(log)
    db.commit()
    db.refresh(log)

    try:
        fetched = fetch_all_news()
        new_count = 0
        for item in fetched:
            exists = db.scalar(select(NewsItem.id).where(NewsItem.url == item["url"]))
            if exists:
                continue
            db.add(
                NewsItem(
                    title=item["title"],
                    summary=item.get("summary", ""),
                    url=item["url"],
                    source=item.get("source", "未知"),
                    platform=item.get("platform", "综合"),
                    published_at=item.get("published_at", ""),
                    category=item.get("category", "综合"),
                    fetched_at=datetime.utcnow(),
                )
            )
            new_count += 1

        db.commit()
        total = db.scalar(select(func.count()).select_from(NewsItem)) or 0
        log.status = "ok"
        log.new_count = new_count
        log.total_count = total
        log.finished_at = datetime.utcnow()
        log.message = f"抓取 {len(fetched)} 条，新增 {new_count} 条"
        db.commit()
        return {
            "status": "ok",
            "new_count": new_count,
            "fetched_count": len(fetched),
            "total_count": total,
            "message": log.message,
        }
    except Exception as exc:
        log.status = "error"
        log.finished_at = datetime.utcnow()
        log.message = str(exc)
        db.commit()
        return {"status": "error", "message": str(exc)}


def list_news(
    db: Session,
    *,
    platform: Optional[str] = None,
    category: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = 80,
) -> List[NewsItem]:
    stmt = select(NewsItem).order_by(desc(NewsItem.fetched_at), desc(NewsItem.id))
    if platform:
        stmt = stmt.where(NewsItem.platform == platform)
    if category:
        stmt = stmt.where(NewsItem.category == category)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(NewsItem.title.like(like) | NewsItem.summary.like(like))
    return list(db.scalars(stmt.limit(limit)))


def get_stats(db: Session) -> dict:
    total = db.scalar(select(func.count()).select_from(NewsItem)) or 0
    platforms = db.execute(
        select(NewsItem.platform, func.count())
        .group_by(NewsItem.platform)
        .order_by(desc(func.count()))
    ).all()
    categories = db.execute(
        select(NewsItem.category, func.count())
        .group_by(NewsItem.category)
        .order_by(desc(func.count()))
    ).all()
    last_log = db.scalar(select(FetchLog).order_by(desc(FetchLog.id)).limit(1))
    last_fetch = None
    if last_log and last_log.finished_at:
        last_fetch = last_log.finished_at.strftime("%Y-%m-%d %H:%M")
    elif last_log:
        last_fetch = last_log.started_at.strftime("%Y-%m-%d %H:%M")

    return {
        "total": total,
        "platforms": [{"name": name, "count": count} for name, count in platforms],
        "categories": [{"name": name, "count": count} for name, count in categories],
        "last_fetch": last_fetch,
        "last_status": last_log.status if last_log else None,
    }
