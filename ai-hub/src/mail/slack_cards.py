#!/usr/bin/env python3
"""Post email cards to Slack #mail-inbox with approval buttons.

Usage:
    python -m src.mail.slack_cards
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from src.shared.config import load_config, env_opt
from src.shared.slack_client import post_message
from src.shared.db import conn

# Category to emoji mapping
CATEGORY_EMOJI = {
    "urgent": ":rotating_light:",
    "needs_reply": ":email:",
    "info_only": ":information_source:",
    "spam": ":wastebasket:",
}


def build_email_blocks(email_row: dict) -> list:
    """Build Slack Block Kit blocks for one email."""
    cat = email_row["category"] or "info_only"
    emoji = CATEGORY_EMOJI.get(cat, ":email:")
    eid = email_row["id"]

    blocks = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": (
                f"{emoji} *[{cat.upper()}]* {email_row['subject']}\n"
                f"From: `{email_row['from_addr'][:60]}`"
            )},
        },
    ]

    # Show draft reply if available
    if email_row.get("draft_reply"):
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": (
                f"*Draft reply:*\n"
                f">{email_row['draft_reply'][:300].replace(chr(10), chr(10) + '>')}"
            )},
        })

    # Action buttons for needs_reply/urgent
    if cat in ("urgent", "needs_reply") and email_row.get("draft_reply"):
        blocks.append({
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Approve & Send"},
                    "style": "primary",
                    "action_id": f"mail_approve_{eid}",
                    "value": str(eid),
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Ignore"},
                    "action_id": f"mail_ignore_{eid}",
                    "value": str(eid),
                },
            ],
        })
    elif cat == "info_only":
        blocks.append({
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": "_No reply needed_"}],
        })

    blocks.append({"type": "divider"})
    return blocks


def post_pending_emails():
    """Post all unposted classified emails to Slack."""
    cfg = load_config()
    channel = cfg["slack"]["channels"].get("mail_inbox", "") or env_opt("SLACK_CHANNEL_MAIL", "")
    if not channel:
        print("No mail channel configured.")
        return

    with conn() as c:
        rows = c.execute(
            """SELECT * FROM emails
               WHERE category IS NOT NULL AND slack_ts IS NULL AND status = 'pending'
               ORDER BY
                 CASE category
                   WHEN 'urgent' THEN 1
                   WHEN 'needs_reply' THEN 2
                   WHEN 'info_only' THEN 3
                   WHEN 'spam' THEN 4
                 END"""
        ).fetchall()

    if not rows:
        print("No emails to post.")
        return

    for row in rows:
        row_dict = dict(row)
        if row_dict["category"] == "spam":
            # Auto-archive spam
            with conn() as c:
                c.execute("UPDATE emails SET status = 'auto_archived' WHERE id = ?", (row_dict["id"],))
            continue

        blocks = build_email_blocks(row_dict)
        text = f"[{row_dict['category']}] {row_dict['subject']}"
        ts = post_message(channel, text=text, blocks=blocks)

        with conn() as c:
            c.execute("UPDATE emails SET slack_ts = ? WHERE id = ?", (ts, row_dict["id"]))

        print(f"  Posted: [{row_dict['category']}] {row_dict['subject'][:50]}")

    print(f"Posted {len(rows)} emails to Slack")


if __name__ == "__main__":
    post_pending_emails()
