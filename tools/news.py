"""RSS-based search tools for recent international news."""

import re
import sqlite3
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import feedparser
import requests

from .memory import save_news


RSS_FEEDS = {
    "G1": "https://g1.globo.com/rss/g1/brasil/",
    "BBC News": "https://feeds.bbci.co.uk/news/world/rss.xml",
    "The Guardian": "https://www.theguardian.com/world/rss",
}
REQUEST_HEADERS = {"User-Agent": "NewsRadarAI/1.0 (+RSS reader)"}


def _normalize_title(title: str) -> str:
    """Normalize a headline for simple duplicate detection."""
    return re.sub(r"[^a-z0-9]+", " ", title.casefold()).strip()


def _normalize_url(url: str) -> str:
    """Remove common tracking parameters and URL fragments."""
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), "", ""))


def search_news(query: str = "", limit: int = 10) -> dict[str, Any]:
    """Search recent headlines from BBC News, The Guardian, and Al Jazeera.

    Args:
        query: Optional words to find in each headline or its summary.
        limit: Maximum number of unique headlines to return, from 1 to 30.

    Returns:
        A dictionary with a status and the matching news items.
    """
    try:
        limit = max(1, min(int(limit), 30))
    except (TypeError, ValueError):
        return {"status": "error", "message": "limit must be an integer."}

    terms = [term for term in re.findall(r"\w+", query.casefold()) if term]
    news: list[dict[str, Any]] = []
    seen_titles: set[str] = set()
    seen_urls: set[str] = set()
    source_errors: list[str] = []

    for source, feed_url in RSS_FEEDS.items():
        try:
            response = requests.get(
                feed_url, headers=REQUEST_HEADERS, timeout=15
            )
            response.raise_for_status()
            feed = feedparser.parse(response.content)
        except requests.RequestException as error:
            source_errors.append(f"{source}: {error}")
            continue

        for entry in feed.entries:
            title = str(entry.get("title", "")).strip()
            url = str(entry.get("link", "")).strip()
            summary = re.sub(r"<[^>]+>", " ", str(entry.get("summary", "")))
            searchable_text = f"{title} {summary}".casefold()
            normalized_title = _normalize_title(title)
            normalized_url = _normalize_url(url)

            if not title or not url:
                continue
            if terms and not all(term in searchable_text for term in terms):
                continue
            if normalized_title in seen_titles or normalized_url in seen_urls:
                continue

            seen_titles.add(normalized_title)
            seen_urls.add(normalized_url)
            news.append(
                {
                    "title": title,
                    "url": url,
                    "published_at": str(entry.get("published", "")),
                    "source": source,
                    "summary": summary.strip(),
                }
            )
            if len(news) >= limit:
                break

        if len(news) >= limit:
            break

    if not news and source_errors:
        return {
            "status": "error",
            "message": "Could not retrieve news from any RSS source.",
            "source_errors": source_errors,
        }

    memory_result: dict[str, Any]
    try:
        memory_result = save_news(news)
        for item, is_new in zip(news, memory_result["is_new"]):
            item["is_new"] = is_new
    except (OSError, sqlite3.Error) as error:
        memory_result = {"memory_error": str(error)}

    result: dict[str, Any] = {
        "status": "success",
        "total": len(news),
        "news": news,
    }
    if "new_count" in memory_result:
        result["new_count"] = memory_result["new_count"]
        result["previously_seen_count"] = memory_result["previously_seen_count"]
        result["memory_status"] = "saved"
    else:
        result["memory_status"] = "error"
        result["memory_error"] = memory_result["memory_error"]
    if source_errors:
        result["source_errors"] = source_errors
    if not news:
        result["message"] = "No matching news found."
    return result
