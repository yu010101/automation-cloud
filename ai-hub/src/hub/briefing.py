#!/usr/bin/env python3
"""Generate unified daily briefing from all projects.

Usage:
    python -m src.hub.briefing
    python -m src.hub.briefing --post  # Post to Slack
"""

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from src.shared.config import load_config, env_opt
from src.shared.slack_client import post_message
from src.shared.db import conn


def _eddie_conn():
    """Get a connection to Eddie's DB (Turso or local SQLite)."""
    if os.getenv("DB_BACKEND", "").lower() == "turso":
        import libsql_experimental as libsql
        url = os.environ["TURSO_EDDIE_URL"]
        token = os.environ["TURSO_EDDIE_TOKEN"]
        c = libsql.connect("eddie.db", sync_url=url, auth_token=token)
        c.sync()
        return c
    else:
        cfg = load_config()
        db_path = Path(cfg["kpi"]["sources"]["eddie"]["db_path"]).expanduser()
        if not db_path.exists():
            return None
        c = sqlite3.connect(str(db_path))
        c.row_factory = sqlite3.Row
        return c


def collect_eddie_kpi() -> dict:
    """Collect KPI from Eddie's database (local SQLite or Turso)."""
    try:
        c = _eddie_conn()
        if c is None:
            return {"status": "offline", "error": "DB not found"}
        today = datetime.now().strftime("%Y-%m-%d")
        total = c.execute("SELECT COUNT(*) FROM influencers").fetchone()[0]
        with_email = c.execute("SELECT COUNT(*) FROM influencers WHERE email IS NOT NULL AND email != ''").fetchone()[0]
        contacted = c.execute("SELECT COUNT(*) FROM influencers WHERE status = 'contacted'").fetchone()[0]
        negotiating = c.execute("SELECT COUNT(*) FROM influencers WHERE status = 'negotiating'").fetchone()[0]
        contracted = c.execute("SELECT COUNT(*) FROM influencers WHERE status = 'contracted'").fetchone()[0]
        sent_today = c.execute("SELECT COUNT(*) FROM outreach_logs WHERE DATE(created_at) = ?", (today,)).fetchone()[0]
        replied_today = c.execute("SELECT COUNT(*) FROM outreach_logs WHERE DATE(reply_at) = ? AND status='replied'", (today,)).fetchone()[0]
        if hasattr(c, 'close'):
            c.close()
        return {
            "status": "online",
            "total_influencers": total,
            "with_email": with_email,
            "contacted": contacted,
            "negotiating": negotiating,
            "contracted": contracted,
            "emails_sent_today": sent_today,
            "replies_today": replied_today,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def collect_cfo_kpi() -> dict:
    """Collect KPI from CFO Agent API."""
    cfg = load_config()
    api_url = os.getenv("CFO_API_URL") or cfg["kpi"]["sources"]["cfo"].get("api_url", "")
    if not api_url:
        return {"status": "not_configured"}
    try:
        resp = httpx.get(f"{api_url}/api/dashboard/summary", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            data["status"] = "online"
            return data
        return {"status": "error", "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"status": "offline", "error": str(e)}


def collect_mail_kpi() -> dict:
    """Collect mail processing KPI from hub DB."""
    try:
        with conn() as c:
            today = datetime.now().strftime("%Y-%m-%d")
            total = c.execute("SELECT COUNT(*) FROM emails WHERE DATE(created_at) = ?", (today,)).fetchone()[0]
            pending = c.execute("SELECT COUNT(*) FROM emails WHERE status = 'pending'").fetchone()[0]
            sent = c.execute("SELECT COUNT(*) FROM emails WHERE status = 'sent' AND DATE(sent_at) = ?", (today,)).fetchone()[0]
            urgent = c.execute("SELECT COUNT(*) FROM emails WHERE category = 'urgent' AND status = 'pending'").fetchone()[0]
            return {"status": "online", "received_today": total, "pending": pending, "sent_today": sent, "urgent_pending": urgent}
    except Exception:
        return {"status": "no_data"}


def collect_approval_kpi() -> dict:
    """Collect approval queue stats."""
    try:
        with conn() as c:
            pending = c.execute("SELECT COUNT(*) FROM approvals WHERE status = 'pending'").fetchone()[0]
            today = datetime.now().strftime("%Y-%m-%d")
            approved_today = c.execute("SELECT COUNT(*) FROM approvals WHERE status IN ('approved','auto_approved') AND DATE(decided_at) = ?", (today,)).fetchone()[0]
            return {"pending": pending, "approved_today": approved_today}
    except Exception:
        return {"pending": 0, "approved_today": 0}


def collect_news_summary() -> dict:
    """Collect today's news summary."""
    try:
        from src.news.summarize import get_latest_summary
        summary = get_latest_summary()
        if summary:
            return {"status": "online", "summary": summary}
        return {"status": "no_data"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def generate_briefing() -> str:
    """Generate the unified daily briefing text."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    eddie = collect_eddie_kpi()
    cfo = collect_cfo_kpi()
    mail = collect_mail_kpi()
    approvals = collect_approval_kpi()
    news = collect_news_summary()

    sections = [f"*Daily Briefing - {now}*\n━━━━━━━━━━━━━━━━━━━━━"]

    # Eddie
    if eddie.get("status") == "online":
        sections.append(
            f"*Influencer Agent (Eddie)*\n"
            f"  DB: {eddie['total_influencers']} total, {eddie['with_email']} with email\n"
            f"  Pipeline: {eddie['contacted']} contacted → {eddie['negotiating']} negotiating → {eddie['contracted']} contracted\n"
            f"  Today: {eddie['emails_sent_today']} sent, {eddie['replies_today']} replies"
        )
    else:
        sections.append(f"*Influencer Agent*: {eddie.get('status', 'offline')}")

    # CFO
    if cfo.get("status") == "online":
        sections.append(f"*CFO Agent*\n  {json.dumps(cfo, ensure_ascii=False)[:200]}")
    elif cfo.get("status") == "not_configured":
        sections.append("*CFO Agent*: API URL未設定")
    else:
        sections.append(f"*CFO Agent*: {cfo.get('status', 'offline')}")

    # Mail
    if mail.get("status") == "online":
        urgent_flag = f" :rotating_light: *{mail['urgent_pending']} urgent*" if mail.get("urgent_pending", 0) > 0 else ""
        sections.append(
            f"*Mail*\n"
            f"  Received: {mail['received_today']} | Pending: {mail['pending']} | Sent: {mail['sent_today']}{urgent_flag}"
        )

    # Approvals
    if approvals["pending"] > 0:
        sections.append(f"*Approvals*\n  :bell: {approvals['pending']} pending | {approvals['approved_today']} approved today")
    else:
        sections.append(f"*Approvals*: All clear ({approvals['approved_today']} approved today)")

    # News
    if news.get("status") == "online" and news.get("summary"):
        sections.append(f"*News Digest*\n{news['summary']}")

    sections.append("━━━━━━━━━━━━━━━━━━━━━")
    return "\n\n".join(sections)


def generate_briefing_blocks() -> list:
    """Generate Slack Block Kit blocks for the briefing."""
    eddie = collect_eddie_kpi()
    cfo = collect_cfo_kpi()
    mail = collect_mail_kpi()
    approvals = collect_approval_kpi()
    news = collect_news_summary()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": f"Daily Briefing - {now}"}},
        {"type": "divider"},
    ]

    # Eddie section
    if eddie.get("status") == "online":
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": (
            f"*:busts_in_silhouette: Influencer Agent*\n"
            f"DB: *{eddie['total_influencers']}* total | *{eddie['with_email']}* with email\n"
            f"Pipeline: {eddie['contacted']} contacted > {eddie['negotiating']} negotiating > *{eddie['contracted']} contracted*\n"
            f"Today: {eddie['emails_sent_today']} sent, {eddie['replies_today']} replies"
        )}})

    # Mail section
    if mail.get("status") == "online":
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": (
            f"*:email: Mail*\n"
            f"Received: *{mail['received_today']}* | Pending: *{mail['pending']}* | Sent: *{mail['sent_today']}*"
            + (f"\n:rotating_light: *{mail['urgent_pending']} urgent pending*" if mail.get("urgent_pending", 0) > 0 else "")
        )}})

    # Approvals section
    blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": (
        f"*:white_check_mark: Approvals*\n"
        f"Pending: *{approvals['pending']}* | Approved today: *{approvals['approved_today']}*"
    )}})

    # News section
    if news.get("status") == "online" and news.get("summary"):
        blocks.append({"type": "divider"})
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": (
            f"*:newspaper: News Digest*\n{news['summary']}"
        )}})

    # Action button
    blocks.append({"type": "actions", "elements": [
        {"type": "button", "text": {"type": "plain_text", "text": "Full Status"}, "action_id": "hub_full_status"},
    ]})

    return blocks


def post_briefing():
    """Post the daily briefing to Slack."""
    cfg = load_config()
    channel = cfg["slack"]["channels"].get("briefing", "")
    if not channel:
        channel = env_opt("SLACK_CHANNEL_BRIEFING", "")
    if not channel:
        print("No briefing channel configured. Printing to console.")
        print(generate_briefing())
        return

    blocks = generate_briefing_blocks()
    text = generate_briefing()  # Fallback for notifications
    ts = post_message(channel, text=text, blocks=blocks)
    print(f"Briefing posted: ts={ts}")


def main():
    parser = argparse.ArgumentParser(description="Generate daily briefing")
    parser.add_argument("--post", action="store_true", help="Post to Slack")
    args = parser.parse_args()

    if args.post:
        post_briefing()
    else:
        print(generate_briefing())


if __name__ == "__main__":
    main()
