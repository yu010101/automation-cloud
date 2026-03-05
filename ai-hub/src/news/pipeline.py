#!/usr/bin/env python3
"""News pipeline: fetch → summarize → (optional) post to Slack.

Usage:
    python -m src.news.pipeline
    python -m src.news.pipeline --post
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from src.news.fetch import fetch_all_feeds, store_articles
from src.news.summarize import get_todays_articles, summarize_articles, get_latest_summary
from src.shared.config import load_config, env_opt
from src.shared.db import conn
from src.shared.slack_client import post_message
from datetime import datetime


def run_pipeline(post_to_slack: bool = False):
    """Run the full news pipeline."""
    # Step 1: Fetch
    print("[1/3] Fetching RSS feeds...")
    articles = fetch_all_feeds()
    new = 0
    if articles:
        new = store_articles(articles)
        print(f"  {new} new articles stored")

    # Step 2: Summarize
    print("[2/3] Summarizing...")
    if new > 0:
        to_summarize = get_todays_articles()
        if to_summarize:
            summary = summarize_articles(to_summarize)
            if summary:
                with conn() as c:
                    c.execute(
                        "INSERT INTO news_summaries (summary_text, article_count, created_at) VALUES (?, ?, ?)",
                        (summary, len(to_summarize), datetime.now().isoformat())
                    )
                print(f"  Summary generated ({len(to_summarize)} articles)")
            else:
                print("  No summary generated")
        else:
            print("  No articles to summarize")
            summary = ""
    else:
        summary = get_latest_summary()
        print(f"  Using existing summary" if summary else "  No summary available")

    # Step 3: Post
    if post_to_slack and summary:
        print("[3/3] Posting to Slack...")
        cfg = load_config()
        channel = cfg["slack"]["channels"].get("briefing", "") or env_opt("SLACK_CHANNEL_BRIEFING", "")
        if channel:
            blocks = [
                {"type": "header", "text": {"type": "plain_text", "text": "News Digest"}},
                {"type": "section", "text": {"type": "mrkdwn", "text": summary}},
            ]
            post_message(channel, text=summary, blocks=blocks)
            print("  Posted to Slack")
        else:
            print("  No Slack channel configured, printing:")
            print(f"\n{summary}")
    elif not post_to_slack and summary:
        print(f"\n--- News Summary ---\n{summary}")
    else:
        print("No news to report")


def main():
    parser = argparse.ArgumentParser(description="News pipeline")
    parser.add_argument("--post", action="store_true", help="Post summary to Slack")
    args = parser.parse_args()
    run_pipeline(post_to_slack=args.post)


if __name__ == "__main__":
    main()
