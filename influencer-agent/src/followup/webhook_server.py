#!/usr/bin/env python3
"""FastAPI webhook server for Smartlead events.

Usage:
    uvicorn src.followup.webhook_server:app --port 8765
"""

import sys
from pathlib import Path

from fastapi import FastAPI, Request

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from src.shared.db import update_outreach_status, update_influencer_status, get_connection
from src.followup.classify import classify_reply
from src.followup.notify import send_telegram

app = FastAPI(title="Eddie Webhook Server")


@app.post("/webhook/smartlead")
async def handle_smartlead_webhook(request: Request):
    """Handle incoming Smartlead webhook events."""
    payload = await request.json()
    event_type = payload.get("event_type", "")
    lead_email = payload.get("sl_lead_email", "") or payload.get("to_email", "")

    print(f"Webhook received: {event_type} for {lead_email}")

    if event_type == "EMAIL_REPLY":
        reply_text = payload.get("preview_text", "")

        # Classify the reply
        category = classify_reply(reply_text)

        # Update local DB
        update_outreach_status(lead_email, "replied", reply_text, category)

        # Find and update influencer status
        with get_connection() as conn:
            row = conn.execute(
                "SELECT instagram_username FROM influencers WHERE email = ?", (lead_email,)
            ).fetchone()
            if row:
                if category in ("interested", "meeting_request"):
                    update_influencer_status(row["instagram_username"], "negotiating")
                    # Send Telegram notification
                    send_telegram(
                        f"*New {category} reply*\n"
                        f"@{row['instagram_username']}\n"
                        f"Email: {lead_email}\n\n"
                        f"_{reply_text[:200]}_"
                    )
                elif category == "not_interested":
                    update_influencer_status(row["instagram_username"], "rejected")

        return {"status": "ok", "category": category}

    elif event_type == "EMAIL_BOUNCE":
        update_outreach_status(lead_email, "bounced")
        return {"status": "ok", "action": "bounced"}

    elif event_type == "LEAD_UNSUBSCRIBED":
        update_outreach_status(lead_email, "unsubscribed")
        return {"status": "ok", "action": "unsubscribed"}

    return {"status": "ok", "action": "ignored"}


@app.get("/health")
async def health():
    return {"status": "ok"}
