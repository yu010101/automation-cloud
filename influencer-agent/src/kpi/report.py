#!/usr/bin/env python3
"""KPI report generation.

Usage:
    python -m src.kpi.report --type daily
    python -m src.kpi.report --type weekly
    python -m src.kpi.report --type daily --notify
"""

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from src.shared.config import load_config
from src.shared.db import get_connection, get_pipeline_counts, get_total_counts
from src.followup.notify import send_telegram
from src.outreach.campaign import get_campaign_stats


def generate_daily_report(notify: bool = False) -> str:
    """Generate daily KPI report."""
    today = datetime.now().strftime("%Y-%m-%d")
    totals = get_total_counts()
    pipeline = get_pipeline_counts()

    with get_connection() as conn:
        # Today's outreach stats
        sent_today = conn.execute(
            "SELECT COUNT(*) FROM outreach_logs WHERE DATE(created_at) = ?", (today,)
        ).fetchone()[0]
        replied_today = conn.execute(
            "SELECT COUNT(*) FROM outreach_logs WHERE DATE(reply_at) = ? AND status = 'replied'", (today,)
        ).fetchone()[0]
        discovered_today = conn.execute(
            "SELECT COUNT(*) FROM influencers WHERE DATE(discovered_at) = ?", (today,)
        ).fetchone()[0]
        interested_today = conn.execute(
            "SELECT COUNT(*) FROM outreach_logs WHERE DATE(reply_at) = ? AND reply_category IN ('interested', 'meeting_request')", (today,)
        ).fetchone()[0]

    # Get Smartlead stats for active campaigns
    sl_stats = {}
    with get_connection() as conn:
        campaigns = conn.execute(
            "SELECT smartlead_campaign_id FROM campaigns WHERE status = 'active'"
        ).fetchall()
    for c in campaigns:
        if c["smartlead_campaign_id"]:
            try:
                stats = get_campaign_stats(c["smartlead_campaign_id"])
                for k, v in stats.items():
                    sl_stats[k] = sl_stats.get(k, 0) + (v if isinstance(v, (int, float)) else 0)
            except Exception as e:
                print(f"Failed to fetch Smartlead stats: {e}")

    open_rate = f"{sl_stats.get('open_rate', 0):.1f}%" if sl_stats.get("open_rate") else "N/A"
    reply_rate = f"{sl_stats.get('reply_rate', 0):.1f}%" if sl_stats.get("reply_rate") else "N/A"

    report = f"""📊 *Daily KPI Report - {today}*
━━━━━━━━━━━━━━━━━━━━━

*Discovery:*
  New influencers found: {discovered_today}
  Total in database: {totals['total']}
  With email: {totals['with_email']}

*Outreach:*
  Emails sent today: {sent_today}
  Open rate: {open_rate}
  Reply rate: {reply_rate}
  Interested leads today: {interested_today}

*Pipeline:*
  Discovered: {pipeline.get('discovered', 0)}
  Contacted: {pipeline.get('contacted', 0)}
  Replied: {pipeline.get('replied', 0)}
  Negotiating: {pipeline.get('negotiating', 0)}
  Contracted: {pipeline.get('contracted', 0)}
  Rejected: {pipeline.get('rejected', 0)}
━━━━━━━━━━━━━━━━━━━━━"""

    if notify:
        send_telegram(report)

    return report


def generate_weekly_report(notify: bool = False) -> str:
    """Generate weekly summary report."""
    today = datetime.now()
    week_ago = (today - timedelta(days=7)).strftime("%Y-%m-%d")
    today_str = today.strftime("%Y-%m-%d")

    with get_connection() as conn:
        sent_week = conn.execute(
            "SELECT COUNT(*) FROM outreach_logs WHERE DATE(created_at) >= ?", (week_ago,)
        ).fetchone()[0]
        replied_week = conn.execute(
            "SELECT COUNT(*) FROM outreach_logs WHERE DATE(reply_at) >= ? AND status = 'replied'", (week_ago,)
        ).fetchone()[0]
        discovered_week = conn.execute(
            "SELECT COUNT(*) FROM influencers WHERE DATE(discovered_at) >= ?", (week_ago,)
        ).fetchone()[0]
        interested_week = conn.execute(
            "SELECT COUNT(*) FROM outreach_logs WHERE DATE(reply_at) >= ? AND reply_category IN ('interested', 'meeting_request')", (week_ago,)
        ).fetchone()[0]

    reply_rate = f"{(replied_week / sent_week * 100):.1f}%" if sent_week > 0 else "N/A"
    conversion = f"{(interested_week / replied_week * 100):.1f}%" if replied_week > 0 else "N/A"
    pipeline = get_pipeline_counts()

    report = f"""📈 *Weekly Summary - {week_ago} to {today_str}*
━━━━━━━━━━━━━━━━━━━━━

*This Week:*
  Influencers discovered: {discovered_week}
  Emails sent: {sent_week}
  Replies received: {replied_week}
  Reply rate: {reply_rate}
  Interested leads: {interested_week}
  Interest conversion: {conversion}

*Pipeline Total:*
  Discovered: {pipeline.get('discovered', 0)}
  Contacted: {pipeline.get('contacted', 0)}
  Negotiating: {pipeline.get('negotiating', 0)}
  Contracted: {pipeline.get('contracted', 0)}
━━━━━━━━━━━━━━━━━━━━━"""

    if notify:
        send_telegram(report)

    return report


def main():
    parser = argparse.ArgumentParser(description="KPI report generation")
    parser.add_argument("--type", required=True, choices=["daily", "weekly"])
    parser.add_argument("--notify", action="store_true", help="Send to Telegram")
    args = parser.parse_args()

    if args.type == "daily":
        report = generate_daily_report(args.notify)
    else:
        report = generate_weekly_report(args.notify)
    print(report)


if __name__ == "__main__":
    main()
