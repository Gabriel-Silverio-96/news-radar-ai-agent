"""Scheduled daily news research and reporting job."""

import json
import time
from datetime import datetime
from typing import Any

from .google_drive import save_news_report
from .memory import finish_job_run, start_job_run
from .research import research_news


def _build_report(result: dict[str, Any]) -> tuple[str, int]:
    """Format a source-linked daily report from retrieved research results."""
    generated_at = datetime.now().astimezone()
    lines = [
        "NEWS RADAR AI - DAILY BRIEFING",
        f"Generated: {generated_at.strftime('%Y-%m-%d %H:%M %Z')}",
        "",
        "This report includes headlines and article text retrieved from the linked sources.",
        "The extracted text has not been independently fact-checked.",
        "",
    ]

    freshness_verified = result.get("freshness_verified", False)
    if freshness_verified:
        headlines = result.get("new_headlines", [])
        if headlines:
            lines.append(f"New headlines: {len(headlines)}")
        else:
            lines.append("No headlines new to local history were found today.")
        lines.append(
            f"Previously seen headlines in this search: {result.get('previously_seen_count', 0)}"
        )
    else:
        headlines = result.get("headlines_for_review", [])
        lines.append(
            "Local history could not verify which results are new; freshness is unknown."
        )

    articles_by_url = {article.get("url"): article for article in result.get("articles", [])}
    for index, item in enumerate(headlines, start=1):
        lines.extend(
            [
                "",
                f"{index}. {item.get('title', 'Untitled headline')}",
                f"Source: {item.get('source', 'Unknown')}",
                f"Published: {item.get('published_at') or 'Not provided by source'}",
                f"Link: {item.get('url', '')}",
            ]
        )
        article = articles_by_url.get(item.get("url"))
        if article:
            excerpt = " ".join(article.get("content", "").split())[:1200]
            lines.extend(["Extracted article excerpt:", excerpt])

    errors = result.get("errors", [])
    if result.get("status") == "error" and result.get("message"):
        lines.extend(["", f"Research status: {result['message']}"])
    if errors:
        lines.extend(["", "Retrieval issues:"])
        for error in errors:
            lines.append(f"- {error.get('url', '')}: {error.get('message', 'Unknown error')}")

    headline_count = len(headlines) + (
        result.get("previously_seen_count", 0) if freshness_verified else 0
    )
    return "\n".join(lines), headline_count


def run_daily_news_job() -> dict[str, Any]:
    """Run a bounded news search, create its Drive report, and record metrics."""
    started_clock = time.monotonic()
    run_id = start_job_run()
    metrics: dict[str, Any] = {}
    try:
        research_result = research_news(headline_limit=5, article_limit=3)
        report_text, headlines_found = _build_report(research_result)
        report_result = save_news_report(report_text)

        freshness_verified = research_result.get("freshness_verified", False)
        new_headlines = (
            len(research_result.get("new_headlines", [])) if freshness_verified else 0
        )
        articles_read = len(research_result.get("articles", []))
        report_succeeded = report_result.get("status") == "success"
        research_succeeded = research_result.get("status") == "success"
        status = "success" if report_succeeded and research_succeeded else "partial"
        if report_result.get("status") == "error":
            status = "failed"

        error_messages = [
            value
            for value in [
                research_result.get("message", ""),
                report_result.get("message", ""),
                *(item.get("message", "") for item in research_result.get("errors", [])),
            ]
            if value
        ]
        metrics = {
            "headlines_found": headlines_found,
            "new_headlines": new_headlines,
            "articles_read": articles_read,
            "document_id": report_result.get("document_id", ""),
            "document_url": report_result.get("url", ""),
            "error": " | ".join(error_messages),
        }
        result = {
            "status": status,
            "run_id": run_id,
            "research": research_result,
            "report": report_result,
        }
    except Exception as error:
        metrics = {"error": str(error)}
        result = {
            "status": "failed",
            "run_id": run_id,
            "message": "The daily news job failed unexpectedly.",
            "error": str(error),
        }

    duration_ms = int((time.monotonic() - started_clock) * 1000)
    try:
        finish_job_run(
            run_id,
            status=result["status"],
            duration_ms=duration_ms,
            **metrics,
        )
    except Exception as error:
        result["monitoring_error"] = str(error)

    return result


def main() -> None:
    """Run the daily job once and print its result as JSON."""
    result = run_daily_news_job()
    research_result = result.get("research", {})
    report_result = result.get("report", {})
    freshness_verified = research_result.get("freshness_verified", False)
    headlines_found = (
        len(research_result.get("new_headlines", []))
        + research_result.get("previously_seen_count", 0)
        if freshness_verified
        else len(research_result.get("headlines_for_review", []))
    )
    summary = {
        "status": result.get("status"),
        "run_id": result.get("run_id"),
        "headlines_found": headlines_found,
        "new_headlines": len(research_result.get("new_headlines", [])),
        "articles_read": len(research_result.get("articles", [])),
        "report_url": report_result.get("url", ""),
        "error": result.get("error") or report_result.get("message", ""),
        "monitoring_error": result.get("monitoring_error", ""),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
