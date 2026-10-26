"""Article retrieval tool for news URLs."""

from typing import Any

import requests
from bs4 import BeautifulSoup

from .news import REQUEST_HEADERS


def get_article(url: str) -> dict[str, Any]:
    """Fetch and extract readable text from a news article URL.

    Args:
        url: The article URL to retrieve, usually returned by search_news.

    Returns:
        A dictionary containing the article title, URL, and extracted text.
    """
    if not url.startswith(("https://", "http://")):
        return {"status": "error", "message": "url must be an HTTP or HTTPS URL."}

    try:
        response = requests.get(
            url,
            headers=REQUEST_HEADERS,
            timeout=20,
            allow_redirects=True,
        )
        response.raise_for_status()
    except requests.RequestException as error:
        return {"status": "error", "url": url, "message": str(error)}

    soup = BeautifulSoup(response.content, "html.parser")
    for element in soup.select(
        "script, style, nav, footer, header, aside, form, noscript, figure"
    ):
        element.decompose()

    article = soup.find("article") or soup.find("main") or soup
    paragraphs = [
        paragraph.get_text(" ", strip=True)
        for paragraph in article.find_all("p")
    ]
    content = "\n\n".join(text for text in paragraphs if text)
    title_tag = soup.find("h1") or soup.find("title")
    title = title_tag.get_text(" ", strip=True) if title_tag else ""

    if not content:
        return {
            "status": "error",
            "url": response.url,
            "title": title,
            "message": "Could not extract article text from this page.",
        }

    return {
        "status": "success",
        "url": response.url,
        "title": title,
        "content": content[:20000],
        "truncated": len(content) > 20000,
    }
