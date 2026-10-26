"""SQLite persistence for news items seen by the agent."""

import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit


DEFAULT_DATABASE_PATH = Path(__file__).resolve().parents[1] / "news_history.db"


def _database_path() -> Path:
    configured_path = os.getenv("NEWS_DB_PATH")
    return Path(configured_path).expanduser() if configured_path else DEFAULT_DATABASE_PATH


@contextmanager
def _connect():
    database_path = _database_path()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path, timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                canonical_url TEXT NOT NULL UNIQUE,
                normalized_title TEXT NOT NULL,
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                source TEXT NOT NULL,
                published_at TEXT NOT NULL DEFAULT '',
                summary TEXT NOT NULL DEFAULT '',
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_news_last_seen_at ON news(last_seen_at)"
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS job_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                status TEXT NOT NULL,
                headlines_found INTEGER NOT NULL DEFAULT 0,
                new_headlines INTEGER NOT NULL DEFAULT 0,
                articles_read INTEGER NOT NULL DEFAULT 0,
                document_id TEXT NOT NULL DEFAULT '',
                document_url TEXT NOT NULL DEFAULT '',
                error TEXT NOT NULL DEFAULT '',
                duration_ms INTEGER
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_job_runs_started_at ON job_runs(started_at)"
        )
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _canonical_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit(
        (parts.scheme.casefold(), parts.netloc.casefold(), parts.path.rstrip("/"), "", "")
    )


def _normalized_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", title.casefold()).strip()


def save_news(items: list[dict[str, str]]) -> dict[str, Any]:
    """Save search results and label each item as new or previously seen."""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    statuses: list[bool] = []

    with _connect() as connection:
        for item in items:
            url = item.get("url", "").strip()
            title = item.get("title", "").strip()
            if not url or not title:
                statuses.append(False)
                continue

            canonical_url = _canonical_url(url)
            normalized_title = _normalized_title(title)
            existing = connection.execute(
                """SELECT id FROM news
                   WHERE canonical_url = ? OR normalized_title = ?
                   LIMIT 1""",
                (canonical_url, normalized_title),
            ).fetchone()
            statuses.append(existing is None)

            if existing:
                connection.execute(
                    """UPDATE news
                       SET last_seen_at = ?, summary = CASE WHEN ? != '' THEN ? ELSE summary END
                       WHERE id = ?""",
                    (now, item.get("summary", ""), item.get("summary", ""), existing["id"]),
                )
            else:
                connection.execute(
                    """INSERT INTO news (
                           canonical_url, normalized_title, title, url, source,
                           published_at, summary, first_seen_at, last_seen_at
                       ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        canonical_url,
                        normalized_title,
                        title,
                        url,
                        item.get("source", "Unknown"),
                        item.get("published_at", ""),
                        item.get("summary", ""),
                        now,
                        now,
                    ),
                )

    return {
        "new_count": sum(statuses),
        "previously_seen_count": len(statuses) - sum(statuses),
        "is_new": statuses,
    }


def get_news_history(query: str = "", limit: int = 10) -> dict[str, Any]:
    """Retrieve recently seen news from the local SQLite database.

    Args:
        query: Optional words to match in saved titles or summaries.
        limit: Maximum number of saved items to return, from 1 to 50.

    Returns:
        A dictionary containing saved news ordered by most recently seen.
    """
    try:
        limit = max(1, min(int(limit), 50))
    except (TypeError, ValueError):
        return {"status": "error", "message": "limit must be an integer."}

    terms = [term for term in re.findall(r"\w+", query.casefold()) if term]
    try:
        with _connect() as connection:
            query_clause = " AND ".join(
                "lower(title || ' ' || summary) LIKE ?" for _ in terms
            )
            sql = """SELECT title, url, source, published_at, summary,
                            first_seen_at, last_seen_at
                     FROM news"""
            parameters: list[Any] = []
            if query_clause:
                sql += f" WHERE {query_clause}"
                parameters.extend(f"%{term}%" for term in terms)
            sql += " ORDER BY last_seen_at DESC LIMIT ?"
            parameters.append(limit)
            rows = connection.execute(sql, parameters).fetchall()
    except (OSError, sqlite3.Error) as error:
        return {"status": "error", "message": f"Could not read news history: {error}"}

    news = [dict(row) for row in rows]
    return {"status": "success", "total": len(news), "news": news}


def start_job_run() -> int:
    """Create a monitoring record for a scheduled job run."""
    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _connect() as connection:
        cursor = connection.execute(
            "INSERT INTO job_runs (started_at, status) VALUES (?, 'running')",
            (started_at,),
        )
        return int(cursor.lastrowid)


def finish_job_run(
    run_id: int,
    *,
    status: str,
    headlines_found: int = 0,
    new_headlines: int = 0,
    articles_read: int = 0,
    document_id: str = "",
    document_url: str = "",
    error: str = "",
    duration_ms: int = 0,
) -> None:
    """Complete a monitoring record with the run outcome and metrics."""
    finished_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _connect() as connection:
        connection.execute(
            """UPDATE job_runs SET finished_at = ?, status = ?, headlines_found = ?,
                   new_headlines = ?, articles_read = ?, document_id = ?,
                   document_url = ?, error = ?, duration_ms = ? WHERE id = ?""",
            (
                finished_at,
                status,
                headlines_found,
                new_headlines,
                articles_read,
                document_id,
                document_url,
                error[:2000],
                duration_ms,
                run_id,
            ),
        )


def get_job_metrics(days: int = 7, limit: int = 20) -> dict[str, Any]:
    """Return daily-job totals and recent run records.

    Args:
        days: Number of days to include, from 1 to 90.
        limit: Maximum number of recent runs to return, from 1 to 50.

    Returns:
        Aggregate metrics and recent scheduled job runs.
    """
    try:
        days = max(1, min(int(days), 90))
        limit = max(1, min(int(limit), 50))
    except (TypeError, ValueError):
        return {"status": "error", "message": "days and limit must be integers."}

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(
        timespec="seconds"
    )
    try:
        with _connect() as connection:
            totals = connection.execute(
                """SELECT COUNT(*) AS runs,
                          COALESCE(SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END), 0) AS successes,
                          COALESCE(SUM(CASE WHEN status != 'success' AND status != 'running' THEN 1 ELSE 0 END), 0) AS failures,
                          COALESCE(SUM(headlines_found), 0) AS headlines_found,
                          COALESCE(SUM(new_headlines), 0) AS new_headlines,
                          COALESCE(SUM(articles_read), 0) AS articles_read,
                          COALESCE(AVG(duration_ms), 0) AS average_duration_ms
                   FROM job_runs WHERE started_at >= ?""",
                (cutoff,),
            ).fetchone()
            rows = connection.execute(
                """SELECT id, started_at, finished_at, status, headlines_found,
                          new_headlines, articles_read, document_id, document_url,
                          error, duration_ms
                   FROM job_runs WHERE started_at >= ?
                   ORDER BY id DESC LIMIT ?""",
                (cutoff, limit),
            ).fetchall()
    except (OSError, sqlite3.Error) as error:
        return {"status": "error", "message": f"Could not read job metrics: {error}"}

    return {
        "status": "success",
        "period_days": days,
        "totals": dict(totals),
        "recent_runs": [dict(row) for row in rows],
    }
