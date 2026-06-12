from __future__ import annotations

import hashlib
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any
from urllib.parse import quote_plus

import httpx

from app.config import settings

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

KEYWORDS = [k.strip() for k in settings.refresh_keywords.split(",") if k.strip()]


def _clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _item(
    *,
    title: str,
    url: str,
    summary: str = "",
    source: str = "未知",
    platform: str = "综合",
    published_at: str = "",
    category: str = "综合",
) -> dict[str, str]:
    title = _clean(title)
    if not title or not url:
        return {}
    if len(summary) > 220:
        summary = summary[:217] + "..."
    return {
        "title": title,
        "url": url.strip(),
        "summary": _clean(summary) or title,
        "source": source,
        "platform": platform,
        "published_at": published_at,
        "category": category,
    }


def _dedupe_key(item: dict[str, str]) -> str:
    raw = (item.get("title") or "") + (item.get("url") or "")
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def _fetch_google_news(client: httpx.Client, keyword: str, limit: int) -> list[dict[str, str]]:
    query = quote_plus(f"{keyword} 上海")
    url = (
        "https://news.google.com/rss/search"
        f"?q={query}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
    )
    response = client.get(url)
    response.raise_for_status()
    root = ET.fromstring(response.text)
    items: list[dict[str, str]] = []
    for node in root.findall("./channel/item")[:limit]:
        title = node.findtext("title") or ""
        link = node.findtext("link") or ""
        pub = node.findtext("pubDate") or ""
        source = node.findtext("source") or "Google 新闻"
        summary = node.findtext("description") or ""
        parsed = _item(
            title=title,
            url=link,
            summary=summary,
            source=source,
            platform="Google",
            published_at=pub,
            category="全网",
        )
        if parsed:
            items.append(parsed)
    return items


def _fetch_baidu_news(client: httpx.Client, keyword: str, limit: int) -> list[dict[str, str]]:
    url = f"https://www.baidu.com/s?rtt=1&bsst=1&cl=2&tn=news&word={quote_plus(keyword)}"
    response = client.get(url)
    response.raise_for_status()
    html = response.text
    items: list[dict[str, str]] = []

    pattern = re.compile(
        r'<div class="result-op c-container xpath-log new-pmd".*?>.*?'
        r'<a[^>]+href="([^"]+)"[^>]*class="news-title-font[^"]*"[^>]*>(.*?)</a>.*?'
        r'<span class="c-color-text"[^>]*>(.*?)</span>',
        re.DOTALL,
    )
    for match in pattern.finditer(html):
        link, title_html, source_html = match.groups()
        parsed = _item(
            title=title_html,
            url=link,
            source=_clean(source_html) or "百度新闻",
            platform="百度",
            category="资讯",
        )
        if parsed:
            items.append(parsed)
        if len(items) >= limit:
            break

    if items:
        return items

    fallback = re.compile(
        r'<h3 class="news-title[^"]*">\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
        re.DOTALL,
    )
    for match in fallback.finditer(html):
        link, title_html = match.groups()
        parsed = _item(
            title=title_html,
            url=link,
            source="百度新闻",
            platform="百度",
            category="资讯",
        )
        if parsed:
            items.append(parsed)
        if len(items) >= limit:
            break
    return items


def _fetch_bing_news(client: httpx.Client, keyword: str, limit: int) -> list[dict[str, str]]:
    query = quote_plus(f"{keyword} 上海")
    url = f"https://www.bing.com/news/search?q={query}&format=rss"
    response = client.get(url)
    response.raise_for_status()
    root = ET.fromstring(response.text)
    items: list[dict[str, str]] = []
    for node in root.findall("./channel/item")[:limit]:
        title = node.findtext("title") or ""
        link = node.findtext("link") or ""
        pub = node.findtext("pubDate") or ""
        summary = node.findtext("description") or ""
        parsed = _item(
            title=title,
            url=link,
            summary=summary,
            source="Bing 新闻",
            platform="Bing",
            published_at=pub,
            category="全网",
        )
        if parsed:
            items.append(parsed)
    return items


def _fetch_gov_baoshan(client: httpx.Client, limit: int) -> list[dict[str, str]]:
    url = "https://www.baoshan.sh.cn/xxgk-fzlm/xxgk-xxgkml/xxgk-xxgkml-zfxxgkml/xxgk-xxgkml-zfxxgkml-zfxxgkml/xxgk-xxgkml-zfxxgkml-zfxxgkml-zfxxgkml/2024zfwj/index.html"
    items: list[dict[str, str]] = []
    try:
        response = client.get("https://www.baoshan.sh.cn/search.html", params={"q": "大场"})
        response.raise_for_status()
        html = response.text
    except Exception:
        return items

    pattern = re.compile(
        r'<a[^>]+href="(/[^"]+)"[^>]*title="([^"]+)"',
        re.IGNORECASE,
    )
    for match in pattern.finditer(html):
        path, title = match.groups()
        if "大场" not in title:
            continue
        parsed = _item(
            title=title,
            url=f"https://www.baoshan.sh.cn{path}",
            source="宝山区政府",
            platform="政务",
            category="政务",
        )
        if parsed:
            items.append(parsed)
        if len(items) >= limit:
            break
    return items


def fetch_all_news() -> list[dict[str, str]]:
    limit = settings.news_per_source
    seen: set[str] = set()
    collected: list[dict[str, str]] = []

    with httpx.Client(timeout=25.0, headers=HEADERS, follow_redirects=True) as client:
        sources: list[tuple[str, Any]] = []
        for keyword in KEYWORDS:
            sources.append(("google", lambda c, k=keyword: _fetch_google_news(c, k, limit)))
            sources.append(("baidu", lambda c, k=keyword: _fetch_baidu_news(c, k, limit)))
            sources.append(("bing", lambda c, k=keyword: _fetch_bing_news(c, k, limit)))
        sources.append(("gov", lambda c: _fetch_gov_baoshan(c, limit)))

        for index, (_, fetcher) in enumerate(sources):
            if index > 0:
                time.sleep(0.4)
            try:
                batch = fetcher(client)
            except Exception:
                batch = []
            for item in batch:
                key = _dedupe_key(item)
                if key in seen:
                    continue
                seen.add(key)
                collected.append(item)

    collected.sort(
        key=lambda x: x.get("published_at") or "",
        reverse=True,
    )
    return collected


def now_label() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")
