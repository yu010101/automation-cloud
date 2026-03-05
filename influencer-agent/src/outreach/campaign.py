#!/usr/bin/env python3
"""Smartlead campaign management.

Usage:
    python -m src.outreach.campaign --action create --name "Q1 Outreach" --niche "fitness"
    python -m src.outreach.campaign --action status --campaign-id 123
    python -m src.outreach.campaign --action list
"""

import argparse
import json
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from src.shared.config import get_env, load_config
from src.shared.db import create_campaign as db_create_campaign

SMARTLEAD_BASE = "https://server.smartlead.ai/api/v1"


def _api(method: str, endpoint: str, json_body: dict | None = None) -> dict:
    """Make a Smartlead API request."""
    api_key = get_env("SMARTLEAD_API_KEY")
    url = f"{SMARTLEAD_BASE}{endpoint}"
    params = {"api_key": api_key}
    resp = requests.request(method, url, params=params, json=json_body, timeout=30)
    resp.raise_for_status()
    return resp.json()


def create_campaign(name: str, niche: str) -> dict:
    """Create a Smartlead campaign and save to local DB."""
    config = load_config()
    outreach_cfg = config.get("outreach", {})

    # Create on Smartlead
    sl_result = _api("POST", "/campaigns/create", {"name": name})
    sl_campaign_id = sl_result.get("id")
    print(f"Smartlead campaign created: ID={sl_campaign_id}")

    # Set schedule
    _api("POST", f"/campaigns/{sl_campaign_id}/schedule", {
        "timezone": config.get("kpi", {}).get("timezone", "America/New_York"),
        "days_of_week": [1, 2, 3, 4, 5],  # Mon-Fri
        "start_hour": "09:00",
        "end_hour": "17:00",
        "min_time_btw_emails": 3,
        "max_new_leads_per_day": outreach_cfg.get("daily_email_limit", 1000) // 34,  # per account
    })

    # Set email sequences from config templates
    sequences = _build_sequences(outreach_cfg)
    _api("POST", f"/campaigns/{sl_campaign_id}/sequences", {"sequences": sequences})

    # Setup webhook for replies
    webhook_url = outreach_cfg.get("webhook_url", "")
    if webhook_url:
        _api("POST", f"/campaigns/{sl_campaign_id}/webhooks", {
            "name": f"Eddie webhook - {name}",
            "webhook_url": webhook_url,
            "event_types": ["EMAIL_REPLY", "EMAIL_BOUNCE", "LEAD_UNSUBSCRIBED", "LEAD_CATEGORY_UPDATED"],
        })

    # Save to local DB
    local_id = db_create_campaign(name, niche, sl_campaign_id)

    return {
        "local_id": local_id,
        "smartlead_id": sl_campaign_id,
        "name": name,
        "niche": niche,
    }


def _build_sequences(outreach_cfg: dict) -> list[dict]:
    """Build email sequence configuration for Smartlead."""
    sequences = [
        {"seq_number": 1, "seq_delay_details": {"delay_in_days": 0}, "subject": "{{subject}}", "email_body": "{{body}}"},
    ]
    follow_ups = outreach_cfg.get("follow_up_sequence", [])
    for i, fu in enumerate(follow_ups, 2):
        sequences.append({
            "seq_number": i,
            "seq_delay_details": {"delay_in_days": fu.get("delay_days", 3)},
            "subject": "",  # empty = reply to previous
            "email_body": f"{{{{followup_{i - 1}_body}}}}",
        })
    return sequences


def get_campaign_stats(campaign_id: int) -> dict:
    """Get analytics for a campaign."""
    return _api("GET", f"/campaigns/{campaign_id}/analytics")


def list_campaigns() -> list[dict]:
    """List all Smartlead campaigns."""
    return _api("GET", "/campaigns")


def main():
    parser = argparse.ArgumentParser(description="Smartlead campaign management")
    parser.add_argument("--action", required=True, choices=["create", "status", "list"])
    parser.add_argument("--name", default="")
    parser.add_argument("--niche", default="")
    parser.add_argument("--campaign-id", type=int, default=0)
    args = parser.parse_args()

    if args.action == "create":
        result = create_campaign(args.name, args.niche)
        print(json.dumps(result, indent=2))
    elif args.action == "status":
        result = get_campaign_stats(args.campaign_id)
        print(json.dumps(result, indent=2))
    elif args.action == "list":
        result = list_campaigns()
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
