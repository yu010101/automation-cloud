#!/usr/bin/env python3
"""Auto-approval rule engine - analyzes patterns and enables auto-approval.

Usage:
    python -m src.kpi.auto_approve --report
    python -m src.kpi.auto_approve --enable-pattern HASH
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from src.shared.db import conn, init_db


def get_pattern_report() -> list[dict]:
    """Generate a report of approval patterns for auto-approval candidates."""
    with conn() as c:
        rows = c.execute(
            """SELECT *,
               CASE WHEN times_approved + times_rejected > 0
                    THEN ROUND(times_approved * 100.0 / (times_approved + times_rejected), 1)
                    ELSE 0 END as approval_rate
               FROM approval_patterns
               ORDER BY times_approved + times_rejected DESC"""
        ).fetchall()
    return [dict(r) for r in rows]


def suggest_auto_approvals() -> list[dict]:
    """Suggest patterns that could be safely auto-approved.
    Criteria: 5+ approvals, 0 rejections, not already enabled."""
    with conn() as c:
        rows = c.execute(
            """SELECT * FROM approval_patterns
               WHERE times_approved >= 5 AND times_rejected = 0 AND auto_approve_enabled = FALSE"""
        ).fetchall()
    return [dict(r) for r in rows]


def enable_auto_approve(condition_hash: str):
    """Enable auto-approval for a specific pattern."""
    with conn() as c:
        c.execute(
            "UPDATE approval_patterns SET auto_approve_enabled = TRUE, updated_at = CURRENT_TIMESTAMP WHERE condition_hash = ?",
            (condition_hash,),
        )
    print(f"Auto-approval enabled for pattern: {condition_hash}")


def disable_auto_approve(condition_hash: str):
    """Disable auto-approval for a specific pattern."""
    with conn() as c:
        c.execute(
            "UPDATE approval_patterns SET auto_approve_enabled = FALSE, updated_at = CURRENT_TIMESTAMP WHERE condition_hash = ?",
            (condition_hash,),
        )
    print(f"Auto-approval disabled for pattern: {condition_hash}")


def weekly_report() -> str:
    """Generate weekly auto-approval analysis report."""
    patterns = get_pattern_report()
    suggestions = suggest_auto_approvals()

    lines = ["*Weekly Approval Pattern Report*", "━━━━━━━━━━━━━━━━━━━━━", ""]

    if patterns:
        lines.append("*All Patterns:*")
        for p in patterns[:10]:
            status = "AUTO" if p["auto_approve_enabled"] else "manual"
            lines.append(
                f"  [{status}] {p['source']}/{p['action_type']}: "
                f"{p['times_approved']}A/{p['times_rejected']}R ({p['approval_rate']}% approval)"
            )
    else:
        lines.append("No patterns yet. Approval history will build over time.")

    if suggestions:
        lines.append(f"\n*Suggested for Auto-Approval ({len(suggestions)}):*")
        for s in suggestions:
            lines.append(
                f"  {s['source']}/{s['action_type']}: {s['times_approved']} consecutive approvals"
                f" → hash: `{s['condition_hash']}`"
            )
        lines.append("\nEnable with: `python -m src.kpi.auto_approve --enable-pattern HASH`")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", action="store_true")
    parser.add_argument("--suggest", action="store_true")
    parser.add_argument("--enable-pattern", default="")
    parser.add_argument("--disable-pattern", default="")
    args = parser.parse_args()

    init_db()
    if args.report:
        print(weekly_report())
    elif args.suggest:
        for s in suggest_auto_approvals():
            print(f"  {s['source']}/{s['action_type']}: {s['condition_hash']}")
    elif args.enable_pattern:
        enable_auto_approve(args.enable_pattern)
    elif args.disable_pattern:
        disable_auto_approve(args.disable_pattern)


if __name__ == "__main__":
    main()
