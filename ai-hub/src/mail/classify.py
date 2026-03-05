#!/usr/bin/env python3
"""Classify emails using Claude API.

Usage:
    python -m src.mail.classify
"""

import json
import sys
from pathlib import Path

import anthropic

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from src.shared.config import env
from src.shared.db import conn

CATEGORIES = ["urgent", "needs_reply", "info_only", "spam"]

SYSTEM_PROMPT = f"""You are an email classifier for a business owner who runs multiple apps and manages influencer marketing.

Classify each email into exactly one category: {', '.join(CATEGORIES)}

Rules:
- "urgent": Time-sensitive business matters, payment issues, legal, account problems, partnership deadlines
- "needs_reply": Business inquiries, partnership proposals, questions from clients/partners, influencer responses
- "info_only": Newsletters, notifications, receipts, automated reports, social media updates, shipping updates
- "spam": Marketing spam, phishing, unsolicited sales pitches, irrelevant promotions

Output ONLY valid JSON: {{"category": "...", "reason": "one sentence", "suggested_priority": 1-5}}
Priority 1 = highest (urgent), 5 = lowest (spam)."""


def classify_email(from_addr: str, subject: str, body_preview: str) -> dict:
    """Classify a single email."""
    client = anthropic.Anthropic(api_key=env("ANTHROPIC_API_KEY"))
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=100,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"From: {from_addr}\nSubject: {subject}\n\nBody:\n{body_preview[:500]}"}],
    )
    text = response.content[0].text.strip()
    try:
        result = json.loads(text)
        if result.get("category") not in CATEGORIES:
            result["category"] = "info_only"
        return result
    except json.JSONDecodeError:
        # Fallback: extract category from text
        for cat in CATEGORIES:
            if cat in text.lower():
                return {"category": cat, "reason": "parsed from text", "suggested_priority": 3}
        return {"category": "info_only", "reason": "classification failed", "suggested_priority": 3}


def classify_pending():
    """Classify all pending emails that haven't been categorized yet."""
    with conn() as c:
        rows = c.execute(
            "SELECT id, from_addr, subject, body_preview FROM emails WHERE category IS NULL AND status = 'pending'"
        ).fetchall()

    if not rows:
        print("No emails to classify.")
        return []

    results = []
    for row in rows:
        result = classify_email(row["from_addr"], row["subject"], row["body_preview"])
        with conn() as c:
            c.execute(
                "UPDATE emails SET category = ? WHERE id = ?",
                (result["category"], row["id"]),
            )
        results.append({"id": row["id"], "subject": row["subject"], **result})
        print(f"  [{result['category']}] {row['subject'][:60]}")

    return results


if __name__ == "__main__":
    results = classify_pending()
    print(f"\nClassified {len(results)} emails")
