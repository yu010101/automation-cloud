#!/usr/bin/env python3
"""Fetch new emails via Gmail IMAP.

Usage:
    python -m src.mail.fetch
"""

import email
import email.message
import imaplib
import sys
from datetime import datetime, timedelta
from email.header import decode_header
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from src.shared.config import env, load_config
from src.shared.db import conn


def decode_mime_header(header: str) -> str:
    """Decode MIME-encoded email header."""
    if not header:
        return ""
    parts = decode_header(header)
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(part)
    return " ".join(decoded)


def get_body(msg: email.message.Message) -> str:
    """Extract text body from email message."""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")
        # Fallback to HTML
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")[:2000]
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            return payload.decode(charset, errors="replace")
    return ""


def fetch_new_emails() -> list[dict]:
    """Fetch unprocessed emails from Gmail IMAP."""
    cfg = load_config()
    imap_server = cfg["mail"]["imap_server"]
    max_emails = cfg["mail"]["max_emails_per_fetch"]

    address = env("GMAIL_ADDRESS")
    password = env("GMAIL_APP_PASSWORD")

    # Get already-processed message IDs
    with conn() as c:
        processed_ids = {row[0] for row in c.execute("SELECT message_id FROM emails").fetchall()}

    # Connect to IMAP
    mail = imaplib.IMAP4_SSL(imap_server)
    mail.login(address, password)
    mail.select("INBOX")

    # Search for recent emails (last 2 days to catch any missed)
    since_date = (datetime.now() - timedelta(days=2)).strftime("%d-%b-%Y")
    _, data = mail.search(None, f'(SINCE "{since_date}")')
    email_ids = data[0].split()

    # Process newest first, limit to max
    new_emails = []
    for eid in reversed(email_ids[-max_emails * 2:]):
        _, msg_data = mail.fetch(eid, "(RFC822)")
        raw = msg_data[0][1]
        msg = email.message_from_bytes(raw)

        message_id = msg.get("Message-ID", "")
        if not message_id or message_id in processed_ids:
            continue

        from_addr = decode_mime_header(msg.get("From", ""))
        subject = decode_mime_header(msg.get("Subject", ""))
        date_str = msg.get("Date", "")
        body = get_body(msg)

        new_emails.append({
            "message_id": message_id,
            "from_addr": from_addr,
            "subject": subject,
            "body_preview": body[:1000],
            "received_at": date_str,
            "full_body": body,
        })

        if len(new_emails) >= max_emails:
            break

    mail.logout()
    return new_emails


def save_emails(emails: list[dict]):
    """Save fetched emails to the database."""
    with conn() as c:
        for e in emails:
            c.execute(
                """INSERT OR IGNORE INTO emails (message_id, from_addr, subject, body_preview, received_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (e["message_id"], e["from_addr"], e["subject"], e["body_preview"], e["received_at"]),
            )
    return len(emails)


if __name__ == "__main__":
    emails = fetch_new_emails()
    saved = save_emails(emails)
    print(f"Fetched {len(emails)} new emails, saved {saved}")
