#!/usr/bin/env python3
"""Send approved email replies via Gmail SMTP.

Usage:
    python -m src.mail.send --email-id 123
"""

import argparse
import smtplib
import sys
from email.mime.text import MIMEText
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from src.shared.config import env, load_config
from src.shared.db import conn


def send_reply(email_id: int, custom_body: str | None = None) -> bool:
    """Send an approved reply for a specific email."""
    with conn() as c:
        row = c.execute("SELECT * FROM emails WHERE id = ?", (email_id,)).fetchone()
        if not row:
            print(f"Email {email_id} not found")
            return False

    reply_body = custom_body or row["draft_reply"]
    if not reply_body:
        print(f"No reply body for email {email_id}")
        return False

    # Extract reply-to address from From header
    from_addr = row["from_addr"]
    # Parse email address from "Name <email@example.com>" format
    if "<" in from_addr and ">" in from_addr:
        to_addr = from_addr[from_addr.index("<") + 1 : from_addr.index(">")]
    else:
        to_addr = from_addr.strip()

    cfg = load_config()
    gmail_addr = env("GMAIL_ADDRESS")
    gmail_pass = env("GMAIL_APP_PASSWORD")

    # Compose reply
    msg = MIMEText(reply_body, "plain", "utf-8")
    msg["Subject"] = f"Re: {row['subject']}"
    msg["From"] = gmail_addr
    msg["To"] = to_addr
    if row["message_id"]:
        msg["In-Reply-To"] = row["message_id"]
        msg["References"] = row["message_id"]

    # Send via SMTP
    try:
        with smtplib.SMTP(cfg["mail"]["smtp_server"], cfg["mail"]["smtp_port"]) as server:
            server.starttls()
            server.login(gmail_addr, gmail_pass)
            server.send_message(msg)

        # Update status
        with conn() as c:
            c.execute(
                "UPDATE emails SET status = 'sent', sent_at = CURRENT_TIMESTAMP WHERE id = ?",
                (email_id,),
            )
        print(f"Reply sent to {to_addr}")
        return True
    except Exception as e:
        print(f"Send failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--email-id", type=int, required=True)
    parser.add_argument("--body", default=None, help="Custom reply body (overrides draft)")
    args = parser.parse_args()
    send_reply(args.email_id, args.body)


if __name__ == "__main__":
    main()
