#!/usr/bin/env python3
"""Classify influencer email replies using Claude API.

Usage:
    python -m src.followup.classify --check-new
    python -m src.followup.classify --text "Thanks, I'd love to learn more about this partnership"
"""

import argparse
import json
import sys
from pathlib import Path

import anthropic

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from src.shared.config import get_env
from src.shared.db import update_outreach_status, update_influencer_status, get_connection

CATEGORIES = ["interested", "meeting_request", "not_interested", "question", "out_of_office", "wrong_person"]

SYSTEM_PROMPT = f"""You are an email reply classifier for influencer outreach campaigns.
Classify the reply into exactly one of these categories: {', '.join(CATEGORIES)}

Rules:
- "interested": They express interest, want to know more, or ask about compensation details
- "meeting_request": They explicitly ask to schedule a call or meeting
- "not_interested": They decline, say no, or express disinterest
- "question": They ask questions not directly about interest (e.g., "what's the app about?")
- "out_of_office": Auto-replies, vacation messages, or temporary unavailability
- "wrong_person": They say they're not the right person, wrong email, etc.

Output ONLY the category name, nothing else."""


def classify_reply(reply_text: str) -> str:
    """Classify a single reply text. Returns category string."""
    client = anthropic.Anthropic(api_key=get_env("ANTHROPIC_API_KEY"))
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=20,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Classify this reply:\n\n{reply_text}"}],
    )
    category = response.content[0].text.strip().lower()
    if category not in CATEGORIES:
        category = "question"  # default fallback
    return category


def process_new_replies() -> list[dict]:
    """Check for unclassified replies and classify them."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT ol.id, ol.reply_text, ol.influencer_id, i.instagram_username, i.email
               FROM outreach_logs ol
               JOIN influencers i ON ol.influencer_id = i.id
               WHERE ol.status = 'replied' AND ol.reply_category IS NULL AND ol.reply_text IS NOT NULL"""
        ).fetchall()

    if not rows:
        print("No new unclassified replies.")
        return []

    results = []
    for row in rows:
        category = classify_reply(row["reply_text"])
        update_outreach_status(row["email"], "replied", row["reply_text"], category)

        # Update influencer status based on category
        if category in ("interested", "meeting_request"):
            update_influencer_status(row["instagram_username"], "negotiating")
        elif category == "not_interested":
            update_influencer_status(row["instagram_username"], "rejected")

        results.append({
            "username": row["instagram_username"],
            "email": row["email"],
            "category": category,
            "preview": row["reply_text"][:100],
        })
        print(f"  @{row['instagram_username']}: {category}")

    return results


def main():
    parser = argparse.ArgumentParser(description="Classify email replies")
    parser.add_argument("--check-new", action="store_true", help="Process all unclassified replies")
    parser.add_argument("--text", default="", help="Classify a single reply text")
    args = parser.parse_args()

    if args.text:
        category = classify_reply(args.text)
        print(json.dumps({"text": args.text[:100], "category": category}))
    elif args.check_new:
        results = process_new_replies()
        print(json.dumps({"processed": len(results), "results": results}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
