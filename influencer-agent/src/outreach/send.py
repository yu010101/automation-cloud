#!/usr/bin/env python3
"""Send outreach emails via Smartlead API.

Usage:
    python -m src.outreach.send --campaign-id 1 --batch-size 100 --activate
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from src.shared.config import get_env, load_config
from src.shared.db import (
    get_uncontacted_with_email,
    log_outreach,
    update_influencer_status,
    get_connection,
)
from src.outreach.campaign import _api
from src.outreach.personalize import generate_batch


def upload_leads(smartlead_campaign_id: int, emails: list[dict]) -> dict:
    """Upload leads to Smartlead campaign in batches of 100."""
    results = {"uploaded": 0, "duplicates": 0, "invalid": 0}

    for i in range(0, len(emails), 100):
        batch = emails[i : i + 100]
        lead_list = []
        for e in batch:
            lead_list.append({
                "first_name": e.get("first_name", ""),
                "last_name": "",
                "email": e["to_email"],
                "custom_fields": {
                    "instagram_username": e.get("instagram_username", ""),
                    "subject": e["subject"],
                    "body": e["body"],
                },
            })

        resp = _api("POST", f"/campaigns/{smartlead_campaign_id}/leads", {
            "lead_list": lead_list,
            "settings": {
                "ignore_global_block_list": False,
                "ignore_unsubscribe_list": False,
                "ignore_community_bounce_list": False,
                "ignore_duplicate_leads_in_other_campaign": False,
            },
        })

        results["uploaded"] += resp.get("upload_count", 0)
        results["duplicates"] += resp.get("duplicate_count", 0)
        results["invalid"] += resp.get("invalid_email_count", 0)
        print(f"  Batch {i // 100 + 1}: uploaded={resp.get('upload_count', 0)}")

    return results


def activate_campaign(smartlead_campaign_id: int):
    """Set campaign status to STARTED."""
    _api("POST", f"/campaigns/{smartlead_campaign_id}/status", {"status": "STARTED"})
    print(f"Campaign {smartlead_campaign_id} activated.")


def run_send(local_campaign_id: int, batch_size: int = 100, activate: bool = False):
    """Full send pipeline: generate emails → upload → activate."""
    # Get smartlead campaign ID from local DB
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM campaigns WHERE id = ?", (local_campaign_id,)
        ).fetchone()
        if not row:
            print(f"Campaign {local_campaign_id} not found in local DB.")
            return
        sl_campaign_id = row["smartlead_campaign_id"]

    # Generate personalized emails
    emails = generate_batch(local_campaign_id, batch_size)
    if not emails:
        print("No emails to send.")
        return

    # Upload to Smartlead
    print(f"Uploading {len(emails)} leads to Smartlead campaign {sl_campaign_id}...")
    upload_result = upload_leads(sl_campaign_id, emails)

    # Log to local DB and update statuses
    for e in emails:
        log_outreach(e["influencer_id"], local_campaign_id, e["subject"], e["body"])
        update_influencer_status(e["instagram_username"], "contacted")

    # Activate if requested
    if activate:
        activate_campaign(sl_campaign_id)

    result = {
        "campaign_id": local_campaign_id,
        "smartlead_campaign_id": sl_campaign_id,
        "emails_generated": len(emails),
        **upload_result,
        "activated": activate,
    }
    print(json.dumps(result, indent=2))
    return result


def main():
    parser = argparse.ArgumentParser(description="Send outreach emails via Smartlead")
    parser.add_argument("--campaign-id", type=int, required=True, help="Local campaign ID")
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--activate", action="store_true")
    args = parser.parse_args()

    run_send(args.campaign_id, args.batch_size, args.activate)


if __name__ == "__main__":
    main()
