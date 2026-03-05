#!/usr/bin/env python3
"""Collect KPIs from all projects and store snapshots.

Usage:
    python -m src.kpi.collector
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from src.shared.db import conn, init_db
from src.hub.briefing import collect_eddie_kpi, collect_cfo_kpi, collect_mail_kpi, collect_approval_kpi


def store_snapshot(source: str, metrics: dict):
    """Store KPI metrics as snapshots."""
    with conn() as c:
        for name, value in metrics.items():
            if isinstance(value, (int, float)):
                c.execute(
                    "INSERT INTO kpi_snapshots (source, metric_name, metric_value) VALUES (?, ?, ?)",
                    (source, name, value),
                )


def collect_all():
    """Collect and store KPIs from all sources."""
    init_db()
    results = {}

    # Eddie
    eddie = collect_eddie_kpi()
    if eddie.get("status") == "online":
        store_snapshot("eddie", {
            "total_influencers": eddie["total_influencers"],
            "with_email": eddie["with_email"],
            "contacted": eddie["contacted"],
            "negotiating": eddie["negotiating"],
            "contracted": eddie["contracted"],
            "emails_sent_today": eddie["emails_sent_today"],
            "replies_today": eddie["replies_today"],
        })
        results["eddie"] = "ok"
    else:
        results["eddie"] = eddie.get("status", "offline")

    # CFO
    cfo = collect_cfo_kpi()
    if cfo.get("status") == "online":
        # Store whatever numeric fields come back
        numeric_fields = {k: v for k, v in cfo.items() if isinstance(v, (int, float))}
        if numeric_fields:
            store_snapshot("cfo", numeric_fields)
        results["cfo"] = "ok"
    else:
        results["cfo"] = cfo.get("status", "offline")

    # Mail
    mail = collect_mail_kpi()
    if mail.get("status") == "online":
        store_snapshot("mail", {
            "received_today": mail["received_today"],
            "pending": mail["pending"],
            "sent_today": mail["sent_today"],
            "urgent_pending": mail.get("urgent_pending", 0),
        })
        results["mail"] = "ok"

    # Approvals
    approvals = collect_approval_kpi()
    store_snapshot("approvals", {
        "pending": approvals["pending"],
        "approved_today": approvals["approved_today"],
    })
    results["approvals"] = "ok"

    return results


if __name__ == "__main__":
    results = collect_all()
    for source, status in results.items():
        print(f"  {source}: {status}")
