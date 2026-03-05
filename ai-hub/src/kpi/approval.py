#!/usr/bin/env python3
"""Approval flow engine - manages pending approvals across all projects.

Usage:
    python -m src.kpi.approval --action list
    python -m src.kpi.approval --action approve --id 123
    python -m src.kpi.approval --action reject --id 123 --reason "Too expensive"
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from src.shared.db import conn, init_db


def create_approval(source: str, action_type: str, summary: str, data: dict = None) -> int:
    """Create a new approval request. Returns approval ID."""
    with conn() as c:
        cursor = c.execute(
            """INSERT INTO approvals (source, action_type, action_summary, action_data)
               VALUES (?, ?, ?, ?)""",
            (source, action_type, summary, json.dumps(data or {})),
        )
        return cursor.lastrowid


def approve(approval_id: int, decided_by: str = "human", reason: str = ""):
    """Approve an action."""
    with conn() as c:
        c.execute(
            """UPDATE approvals SET status = 'approved', decided_by = ?, decided_at = CURRENT_TIMESTAMP, decision_reason = ?
               WHERE id = ? AND status = 'pending'""",
            (decided_by, reason, approval_id),
        )
    # Update pattern learning
    _update_pattern(approval_id, approved=True)


def reject(approval_id: int, decided_by: str = "human", reason: str = ""):
    """Reject an action."""
    with conn() as c:
        c.execute(
            """UPDATE approvals SET status = 'rejected', decided_by = ?, decided_at = CURRENT_TIMESTAMP, decision_reason = ?
               WHERE id = ? AND status = 'pending'""",
            (decided_by, reason, approval_id),
        )
    _update_pattern(approval_id, approved=False)


def auto_approve_check(source: str, action_type: str, data: dict) -> bool:
    """Check if this action can be auto-approved based on learned patterns."""
    condition_hash = _hash_condition(source, action_type, data)
    with conn() as c:
        pattern = c.execute(
            "SELECT * FROM approval_patterns WHERE condition_hash = ? AND auto_approve_enabled = TRUE",
            (condition_hash,),
        ).fetchone()
        if pattern and pattern["times_approved"] >= 5 and pattern["times_rejected"] == 0:
            return True
    return False


def get_pending(limit: int = 20) -> list[dict]:
    """Get pending approval items."""
    with conn() as c:
        rows = c.execute(
            "SELECT * FROM approvals WHERE status = 'pending' ORDER BY created_at ASC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_stats() -> dict:
    """Get approval statistics."""
    with conn() as c:
        pending = c.execute("SELECT COUNT(*) FROM approvals WHERE status = 'pending'").fetchone()[0]
        approved = c.execute("SELECT COUNT(*) FROM approvals WHERE status = 'approved'").fetchone()[0]
        auto_approved = c.execute("SELECT COUNT(*) FROM approvals WHERE status = 'auto_approved'").fetchone()[0]
        rejected = c.execute("SELECT COUNT(*) FROM approvals WHERE status = 'rejected'").fetchone()[0]
        return {
            "pending": pending,
            "approved": approved,
            "auto_approved": auto_approved,
            "rejected": rejected,
            "total": pending + approved + auto_approved + rejected,
            "auto_rate": f"{auto_approved / max(approved + auto_approved, 1) * 100:.1f}%",
        }


def _hash_condition(source: str, action_type: str, data: dict) -> str:
    """Create a hash of the approval condition for pattern matching."""
    # Use source + action_type + key data fields as the pattern
    key = f"{source}:{action_type}:{sorted(data.keys())}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def _update_pattern(approval_id: int, approved: bool):
    """Update pattern learning data based on approval/rejection."""
    with conn() as c:
        row = c.execute("SELECT source, action_type, action_data FROM approvals WHERE id = ?", (approval_id,)).fetchone()
        if not row:
            return
        data = json.loads(row["action_data"]) if row["action_data"] else {}
        condition_hash = _hash_condition(row["source"], row["action_type"], data)
        existing = c.execute("SELECT id FROM approval_patterns WHERE condition_hash = ?", (condition_hash,)).fetchone()
        if existing:
            field = "times_approved" if approved else "times_rejected"
            c.execute(
                f"UPDATE approval_patterns SET {field} = {field} + 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (existing["id"],),
            )
        else:
            c.execute(
                """INSERT INTO approval_patterns (source, action_type, condition_hash, times_approved, times_rejected)
                   VALUES (?, ?, ?, ?, ?)""",
                (row["source"], row["action_type"], condition_hash, 1 if approved else 0, 0 if approved else 1),
            )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--action", required=True, choices=["list", "approve", "reject", "stats"])
    parser.add_argument("--id", type=int, default=0)
    parser.add_argument("--reason", default="")
    args = parser.parse_args()

    init_db()
    if args.action == "list":
        for a in get_pending():
            print(f"  [{a['id']}] {a['source']}/{a['action_type']}: {a['action_summary']}")
    elif args.action == "approve":
        approve(args.id, "cli", args.reason)
        print(f"Approved #{args.id}")
    elif args.action == "reject":
        reject(args.id, "cli", args.reason)
        print(f"Rejected #{args.id}")
    elif args.action == "stats":
        print(json.dumps(get_stats(), indent=2))


if __name__ == "__main__":
    main()
