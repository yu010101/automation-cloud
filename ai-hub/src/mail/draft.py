#!/usr/bin/env python3
"""Generate reply drafts for emails that need a response.

Usage:
    python -m src.mail.draft
"""

import sys
from pathlib import Path

import anthropic

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from src.shared.config import env
from src.shared.db import conn

SYSTEM_PROMPT = """You are a professional email assistant for a business owner.
Write a concise, professional reply in the same language as the original email.
Keep replies under 150 words. Be polite but direct.
Do NOT include subject line or headers - just the reply body.
Sign off with the sender's name if known, otherwise use a generic professional sign-off."""


def generate_draft(from_addr: str, subject: str, body: str) -> str:
    """Generate a reply draft for one email."""
    client = anthropic.Anthropic(api_key=env("ANTHROPIC_API_KEY"))
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": (
            f"Write a reply to this email:\n\n"
            f"From: {from_addr}\n"
            f"Subject: {subject}\n\n"
            f"{body[:1000]}"
        )}],
    )
    return response.content[0].text.strip()


def draft_pending():
    """Generate drafts for all needs_reply emails without drafts."""
    with conn() as c:
        rows = c.execute(
            """SELECT id, from_addr, subject, body_preview FROM emails
               WHERE category IN ('urgent', 'needs_reply') AND draft_reply IS NULL AND status = 'pending'"""
        ).fetchall()

    if not rows:
        print("No emails need drafts.")
        return []

    results = []
    for row in rows:
        draft = generate_draft(row["from_addr"], row["subject"], row["body_preview"])
        with conn() as c:
            c.execute("UPDATE emails SET draft_reply = ? WHERE id = ?", (draft, row["id"]))
        results.append({"id": row["id"], "subject": row["subject"], "draft_preview": draft[:100]})
        print(f"  Drafted: {row['subject'][:60]}")

    return results


if __name__ == "__main__":
    results = draft_pending()
    print(f"\nGenerated {len(results)} drafts")
