"""Bounded multi-step news research workflow."""

from typing import Any

from .article import get_article
from .news import search_news


MAX_HEADLINES = 10
MAX_ARTICLES = 3


def research_news(query: str = "", headline_limit: int = 5, article_limit: int = 3) -> dict[str, Any]:
    """Search current news, read a bounded number of new articles, and report errors.

    This tool performs a fixed workflow: search RSS sources, select unseen
    results, retrieve a few article pages, and return the results with a trace
    of completed steps. It never fetches more than three article pages.

    Args:
        query: Optional words to search for in current headlines and summaries.
        headline_limit: Number of headlines to retrieve, from 1 to 10.
        article_limit: Number of new articles to read, from 0 to 3.

    Returns:
        Search results, retrieved article text, and any step errors.
    """
    try:
        headline_limit = max(1, min(int(headline_limit), MAX_HEADLINES))
        article_limit = max(0, min(int(article_limit), MAX_ARTICLES))
    except (TypeError, ValueError):
        return {
            "status": "error",
            "message": "headline_limit and article_limit must be integers.",
            "steps": [],
        }

    steps: list[dict[str, Any]] = []
    try:
        search_result = search_news(query=query, limit=headline_limit)
    except Exception as error:
        return {
            "status": "error",
            "message": "The news search step failed unexpectedly.",
            "errors": [str(error)],
            "steps": [{"action": "search_news", "status": "error"}],
        }

    steps.append(
        {
            "action": "search_news",
            "status": search_result.get("status", "error"),
            "headlines_found": search_result.get("total", 0),
        }
    )
    if search_result.get("status") != "success":
        return {
            "status": "error",
            "message": "Could not complete news research because the search failed.",
            "search": search_result,
            "steps": steps,
        }

    news = search_result.get("news", [])
    freshness_verified = search_result.get("memory_status") == "saved"
    new_items = [item for item in news if item.get("is_new") is True]
    # "is_new" means unseen in local storage, not necessarily more recent.
    # Research and reports should still cover all current RSS results.
    article_candidates = news
    articles: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    for item in article_candidates[:article_limit]:
        try:
            article_result = get_article(item["url"])
        except Exception as error:
            errors.append({"url": item.get("url", ""), "message": str(error)})
            continue

        if article_result.get("status") != "success" or not article_result.get("content"):
            errors.append(
                {
                    "url": item.get("url", ""),
                    "message": article_result.get(
                        "message", "Article retrieval returned no readable content."
                    ),
                }
            )
            continue

        articles.append(
            {
                "headline": item["title"],
                "source": item["source"],
                "published_at": item["published_at"],
                "url": item["url"],
                "article_title": article_result.get("title", ""),
                "content": article_result["content"],
                "truncated": article_result.get("truncated", False),
                "content_verified": True,
            }
        )

    steps.append(
        {
            "action": "get_article",
            "status": "success" if not errors else "partial",
            "requested": min(len(article_candidates), article_limit),
            "retrieved": len(articles),
        }
    )

    result: dict[str, Any] = {
        "status": (
            "success"
            if articles or not article_candidates or article_limit == 0
            else "partial"
        ),
        "headlines": news,
        "new_headlines": new_items if freshness_verified else [],
        "headlines_for_review": news if not freshness_verified else [],
        "freshness_verified": freshness_verified,
        "previously_seen_count": search_result.get("previously_seen_count", 0),
        "articles": articles,
        "steps": steps,
        "verification_note": (
            "content_verified confirms readable page text was extracted; "
            "it does not independently verify the article's factual claims."
        ),
    }
    if errors:
        result["errors"] = errors
    if not freshness_verified:
        result["memory_warning"] = search_result.get(
            "memory_error", "News history could not be saved."
        )
    if freshness_verified and not new_items:
        result["message"] = "The search returned no headlines that are new to local history."
    elif article_limit == 0:
        result["message"] = (
            "Headlines were found; article retrieval was disabled by article_limit=0."
        )
    return result
