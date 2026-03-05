#!/usr/bin/env python3
"""Post approval requests to Slack #approvals with action buttons.

Usage:
    python -m src.kpi.slack_approvals
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from src.shared.config import load_config, env_opt
from src.shared.slack_client import post_message, update_message, add_reaction
from src.shared.db import conn
from src.kpi.approval import get_pending, approve, reject

# Source to emoji
SOURCE_EMOJI = {
    "mail": ":email:",
    "eddie": ":busts_in_silhouette:",
    "cfo": ":moneybag:",
    "trading": ":chart_with_upwards_trend:",
}


def build_approval_blocks(item: dict) -> list:
    """Build Slack Block Kit for an approval item."""
    emoji = SOURCE_EMOJI.get(item["source"], ":question:")
    aid = item["id"]
    data = json.loads(item["action_data"]) if item.get("action_data") else {}

    blocks = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": (
                f"{emoji} *Approval Required*\n"
                f"*Source:* {item['source']} | *Type:* {item['action_type']}\n"
                f"*Summary:* {item['action_summary']}"
            )},
        },
    ]

    # Show relevant data preview
    if data:
        preview = json.dumps(data, ensure_ascii=False, indent=2)[:300]
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"```{preview}```"},
        })

    # Action buttons
    blocks.append({
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "Approve"},
                "style": "primary",
                "action_id": f"approval_approve_{aid}",
                "value": str(aid),
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "Reject"},
                "style": "danger",
                "action_id": f"approval_reject_{aid}",
                "value": str(aid),
            },
        ],
    })

    blocks.append({"type": "divider"})
    return blocks


def post_pending_approvals():
    """Post unposted pending approvals to Slack."""
    cfg = load_config()
    channel = cfg["slack"]["channels"].get("approvals", "") or env_opt("SLACK_CHANNEL_APPROVALS", "")
    if not channel:
        print("No approvals channel configured.")
        return

    with conn() as c:
        rows = c.execute(
            "SELECT * FROM approvals WHERE status = 'pending' AND slack_ts IS NULL ORDER BY created_at ASC"
        ).fetchall()

    for row in rows:
        item = dict(row)
        blocks = build_approval_blocks(item)
        text = f"[{item['source']}] {item['action_summary']}"
        ts = post_message(channel, text=text, blocks=blocks)
        with conn() as c:
            c.execute("UPDATE approvals SET slack_ts = ? WHERE id = ?", (ts, item["id"]))
        print(f"  Posted approval #{item['id']}: {item['action_summary'][:50]}")


def handle_slack_action(action_id: str, value: str, user_id: str, channel: str, ts: str):
    """Handle Slack button click for approval/rejection.
    Called by OpenClaw webhook or Slack event handler."""
    approval_id = int(value)

    if "approve" in action_id:
        approve(approval_id, decided_by=user_id)
        update_message(channel, ts, text=f":white_check_mark: Approved by <@{user_id}>")
    elif "reject" in action_id:
        reject(approval_id, decided_by=user_id)
        update_message(channel, ts, text=f":x: Rejected by <@{user_id}>")


if __name__ == "__main__":
    post_pending_approvals()
