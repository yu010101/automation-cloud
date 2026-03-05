"""Tests for ai-hub modules."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.shared.db import init_db, conn
from src.shared.config import load_config
from src.kpi.approval import create_approval, approve, reject, get_pending, get_stats, auto_approve_check


def test_config():
    cfg = load_config()
    assert "slack" in cfg
    assert "mail" in cfg
    assert "kpi" in cfg
    assert "approval" in cfg
    print("  config: PASS")


def test_db_init():
    init_db()
    with conn() as c:
        tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    assert "emails" in tables
    assert "kpi_snapshots" in tables
    assert "approvals" in tables
    assert "approval_patterns" in tables
    assert "news_items" in tables
    assert "news_summaries" in tables
    print("  db_init: PASS")


def test_approval_flow():
    init_db()
    # Create
    aid = create_approval("test", "test_action", "Test approval item", {"key": "value"})
    assert aid > 0

    # Pending
    pending = get_pending()
    assert any(p["id"] == aid for p in pending)

    # Approve
    approve(aid, "test_user", "test reason")
    with conn() as c:
        row = c.execute("SELECT * FROM approvals WHERE id = ?", (aid,)).fetchone()
    assert row["status"] == "approved"
    assert row["decided_by"] == "test_user"

    # Create another and reject
    aid2 = create_approval("test", "test_action2", "Reject test")
    reject(aid2, "test_user", "not needed")
    with conn() as c:
        row = c.execute("SELECT * FROM approvals WHERE id = ?", (aid2,)).fetchone()
    assert row["status"] == "rejected"

    # Stats
    stats = get_stats()
    assert stats["approved"] >= 1
    assert stats["rejected"] >= 1

    # Auto-approve check (should be False - not enough history)
    result = auto_approve_check("test", "test_action", {"key": "value"})
    assert result is False

    # Cleanup
    with conn() as c:
        c.execute("DELETE FROM approvals WHERE source = 'test'")
        c.execute("DELETE FROM approval_patterns WHERE source = 'test'")

    print("  approval_flow: PASS")


def test_email_classify_import():
    from src.mail.classify import CATEGORIES
    assert "urgent" in CATEGORIES
    assert "needs_reply" in CATEGORIES
    assert "info_only" in CATEGORIES
    assert "spam" in CATEGORIES
    print("  email_classify_import: PASS")


def test_briefing_collectors():
    from src.hub.briefing import collect_eddie_kpi, collect_mail_kpi, collect_approval_kpi, collect_news_summary
    # These should not crash even with empty/missing data
    eddie = collect_eddie_kpi()
    assert "status" in eddie
    mail = collect_mail_kpi()
    assert "status" in mail or mail == {"status": "no_data"}
    approvals = collect_approval_kpi()
    assert "pending" in approvals
    news = collect_news_summary()
    assert "status" in news
    print("  briefing_collectors: PASS")


def test_all_imports():
    from src.hub.briefing import generate_briefing
    from src.hub.status import full_status
    from src.mail.fetch import fetch_new_emails
    from src.mail.classify import classify_email
    from src.mail.draft import generate_draft
    from src.mail.send import send_reply
    from src.mail.slack_cards import build_email_blocks
    from src.mail.pipeline import run_pipeline
    from src.kpi.collector import collect_all
    from src.kpi.approval import create_approval, approve, reject
    from src.kpi.slack_approvals import build_approval_blocks
    from src.kpi.auto_approve import weekly_report
    from src.news.fetch import fetch_rss
    from src.news.summarize import get_latest_summary
    from src.news.pipeline import run_pipeline as news_pipeline
    print("  all_imports: PASS")


if __name__ == "__main__":
    print("Running ai-hub tests...")
    test_config()
    test_db_init()
    test_approval_flow()
    test_email_classify_import()
    test_briefing_collectors()
    test_all_imports()
    print("\nAll tests passed!")
