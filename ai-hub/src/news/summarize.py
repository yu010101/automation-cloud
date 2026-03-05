#!/usr/bin/env python3
"""Summarize today's news using Claude API.

Usage:
    python -m src.news.summarize
"""

import sys
from datetime import datetime
from pathlib import Path

import anthropic

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from src.shared.config import load_config, env
from src.shared.db import conn


def get_todays_articles(limit: int = 30) -> list[dict]:
    """Get today's unprocessed articles."""
    today = datetime.now().strftime("%Y-%m-%d")
    with conn() as c:
        rows = c.execute(
            "SELECT id, title, url, summary, feed_name FROM news_items "
            "WHERE DATE(created_at) = ? AND summarized = 0 ORDER BY created_at DESC LIMIT ?",
            (today, limit)
        ).fetchall()
    return [dict(r) for r in rows]


def summarize_articles(articles: list[dict]) -> str:
    """Use Claude to summarize articles into a briefing section."""
    if not articles:
        return ""

    client = anthropic.Anthropic(api_key=env("ANTHROPIC_API_KEY"))

    article_text = "\n".join(
        f"- [{a['feed_name']}] {a['title']}: {a['summary'][:200]}"
        for a in articles
    )

    cfg = load_config()
    language = cfg.get("news", {}).get("language", "ja")
    focus = cfg.get("news", {}).get("focus", "AI, テクノロジー, EC, ビジネス")

    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        messages=[{
            "role": "user",
            "content": (
                f"以下のニュース記事リストから、{focus}に関連する重要なものを最大5件選び、"
                f"日本語で簡潔なブリーフィングにまとめてください。\n"
                f"フォーマット: 各記事1行、記事タイトルと要点のみ。見出し不要。\n\n"
                f"{article_text}"
            )
        }]
    )

    summary = resp.content[0].text.strip()

    # Mark articles as summarized
    with conn() as c:
        ids = [a["id"] for a in articles]
        c.execute(
            f"UPDATE news_items SET summarized = 1 WHERE id IN ({','.join('?' * len(ids))})",
            ids
        )

    return summary


def get_latest_summary() -> str:
    """Get today's summary, or generate if not exists."""
    today = datetime.now().strftime("%Y-%m-%d")
    with conn() as c:
        row = c.execute(
            "SELECT summary_text FROM news_summaries WHERE DATE(created_at) = ? ORDER BY created_at DESC LIMIT 1",
            (today,)
        ).fetchone()
    if row:
        return row[0]

    # Generate new summary
    articles = get_todays_articles()
    if not articles:
        return ""

    summary = summarize_articles(articles)
    if summary:
        with conn() as c:
            c.execute(
                "INSERT INTO news_summaries (summary_text, article_count, created_at) VALUES (?, ?, ?)",
                (summary, len(articles), datetime.now().isoformat())
            )
    return summary


def main():
    articles = get_todays_articles()
    if not articles:
        print("No new articles to summarize")
        return

    print(f"Summarizing {len(articles)} articles...")
    summary = summarize_articles(articles)
    if summary:
        with conn() as c:
            c.execute(
                "INSERT INTO news_summaries (summary_text, article_count, created_at) VALUES (?, ?, ?)",
                (summary, len(articles), datetime.now().isoformat())
            )
        print(f"\n{summary}")
    else:
        print("No summary generated")


if __name__ == "__main__":
    main()
