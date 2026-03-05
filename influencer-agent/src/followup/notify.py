#!/usr/bin/env python3
"""Send Telegram notifications for important events.

Usage:
    python -m src.followup.notify --message "New interested lead: @username"
    python -m src.followup.notify --check-escalations
"""

import argparse
import json
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from src.shared.config import get_env, get_env_optional, load_config
from src.shared.db import get_connection


def send_telegram(message: str) -> bool:
    """Send a message via Telegram Bot API."""
    token = get_env("TELEGRAM_BOT_TOKEN")
    chat_id = get_env("TELEGRAM_CHAT_ID")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    resp = requests.post(url, json={
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown",
    }, timeout=10)
    if resp.status_code == 200:
        return True
    print(f"Telegram send failed: {resp.status_code} {resp.text}")
    return False


def check_and_notify_escalations() -> int:
    """Check for replies needing escalation and send notifications."""
    config = load_config()
    triggers = config.get("notifications", {}).get("escalation_triggers", ["interested", "meeting_request"])

    with get_connection() as conn:
        rows = conn.execute(
            """SELECT ol.reply_category, ol.reply_text, i.instagram_username, i.email, i.followers_count
               FROM outreach_logs ol
               JOIN influencers i ON ol.influencer_id = i.id
               WHERE ol.reply_category IN ({})
               AND ol.reply_at > datetime('now', '-1 hour')
            """.format(",".join(f"'{t}'" for t in triggers))
        ).fetchall()

    if not rows:
        return 0

    for row in rows:
        msg = (
            f"*New {row['reply_category']} lead*\n\n"
            f"@{row['instagram_username']} ({row['followers_count']} followers)\n"
            f"Email: {row['email']}\n\n"
            f"Reply preview:\n_{row['reply_text'][:200]}_"
        )
        send_telegram(msg)

    return len(rows)


def main():
    parser = argparse.ArgumentParser(description="Telegram notifications")
    parser.add_argument("--message", default="", help="Send a custom message")
    parser.add_argument("--check-escalations", action="store_true")
    args = parser.parse_args()

    if args.message:
        ok = send_telegram(args.message)
        print("Sent" if ok else "Failed")
    elif args.check_escalations:
        count = check_and_notify_escalations()
        print(f"Sent {count} escalation notifications")


if __name__ == "__main__":
    main()
