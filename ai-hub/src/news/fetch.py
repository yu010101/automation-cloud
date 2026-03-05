#!/usr/bin/env python3
"""Fetch news from RSS feeds and store in DB.

Usage:
    python -m src.news.fetch
"""

import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from src.shared.config import load_config
from src.shared.db import conn


# RSS namespace map
NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "dc": "http://purl.org/dc/elements/1.1/",
}


def fetch_rss(url: str, timeout: int = 15) -> list[dict]:
    """Parse RSS/Atom feed and return list of articles."""
    try:
        resp = httpx.get(url, timeout=timeout, follow_redirects=True, headers={
            "User-Agent": "AI-Hub-NewsBot/1.0"
        })
        resp.raise_for_status()
    except Exception as e:
        print(f"  WARN: Failed to fetch {url}: {e}")
        return []

    articles = []
    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError:
        print(f"  WARN: Failed to parse XML from {url}")
        return []

    # RSS 2.0
    for item in root.findall(".//item"):
        articles.append({
            "title": (item.findtext("title") or "").strip(),
            "url": (item.findtext("link") or "").strip(),
            "published": item.findtext("pubDate") or item.findtext("dc:date", namespaces=NS) or "",
            "summary": (item.findtext("description") or "")[:500].strip(),
            "source": url,
        })

    # Atom
    if not articles:
        for entry in root.findall("atom:entry", NS):
            link_el = entry.find("atom:link[@rel='alternate']", NS) or entry.find("atom:link", NS)
            articles.append({
                "title": (entry.findtext("atom:title", namespaces=NS) or "").strip(),
                "url": link_el.get("href", "") if link_el is not None else "",
                "published": entry.findtext("atom:published", namespaces=NS) or entry.findtext("atom:updated", namespaces=NS) or "",
                "summary": (entry.findtext("atom:summary", namespaces=NS) or "")[:500].strip(),
                "source": url,
            })

    return articles


def fetch_all_feeds() -> list[dict]:
    """Fetch all configured RSS feeds."""
    cfg = load_config()
    news_cfg = cfg.get("news", {})
    feeds = news_cfg.get("feeds", [])

    if not feeds:
        print("No feeds configured in config.yaml")
        return []

    all_articles = []
    for feed in feeds:
        url = feed if isinstance(feed, str) else feed.get("url", "")
        name = feed.get("name", url) if isinstance(feed, dict) else url.split("/")[2]
        print(f"  Fetching: {name}")
        articles = fetch_rss(url)
        for a in articles:
            a["feed_name"] = name if isinstance(feed, dict) else url.split("/")[2]
        all_articles.extend(articles)

    print(f"  Total: {len(all_articles)} articles from {len(feeds)} feeds")
    return all_articles


def store_articles(articles: list[dict]) -> int:
    """Store articles in DB, dedup by URL. Returns count of new articles."""
    new_count = 0
    with conn() as c:
        for a in articles:
            if not a["url"]:
                continue
            existing = c.execute("SELECT id FROM news_items WHERE url = ?", (a["url"],)).fetchone()
            if existing:
                continue
            c.execute(
                "INSERT INTO news_items (title, url, summary, feed_name, published_at, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (a["title"], a["url"], a["summary"], a.get("feed_name", ""), a.get("published", ""), datetime.now().isoformat())
            )
            new_count += 1
    return new_count


def main():
    print("Fetching news feeds...")
    articles = fetch_all_feeds()
    if articles:
        new = store_articles(articles)
        print(f"Stored {new} new articles ({len(articles) - new} duplicates skipped)")
    else:
        print("No articles fetched")


if __name__ == "__main__":
    main()
