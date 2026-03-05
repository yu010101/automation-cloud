#!/usr/bin/env python3
"""Full email processing pipeline: fetch → classify → draft → post to Slack.

Usage:
    python -m src.mail.pipeline
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from src.shared.db import init_db
from src.mail.fetch import fetch_new_emails, save_emails
from src.mail.classify import classify_pending
from src.mail.draft import draft_pending
from src.mail.slack_cards import post_pending_emails


def run_pipeline():
    """Execute the full email processing pipeline."""
    init_db()

    # Step 1: Fetch
    print("Step 1: Fetching new emails...")
    emails = fetch_new_emails()
    saved = save_emails(emails)
    print(f"  {saved} new emails saved")

    # Step 2: Classify
    print("\nStep 2: Classifying emails...")
    classified = classify_pending()
    print(f"  {len(classified)} emails classified")

    # Step 3: Draft replies
    print("\nStep 3: Generating reply drafts...")
    drafts = draft_pending()
    print(f"  {len(drafts)} drafts generated")

    # Step 4: Post to Slack
    print("\nStep 4: Posting to Slack...")
    post_pending_emails()

    print("\nPipeline complete.")
    return {"fetched": saved, "classified": len(classified), "drafted": len(drafts)}


if __name__ == "__main__":
    result = run_pipeline()
    print(f"\nSummary: {result}")
