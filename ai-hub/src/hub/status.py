#!/usr/bin/env python3
"""On-demand status check for all projects.

Usage:
    python -m src.hub.status
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from src.hub.briefing import collect_eddie_kpi, collect_cfo_kpi, collect_mail_kpi, collect_approval_kpi


def full_status() -> dict:
    """Collect status from all projects."""
    return {
        "eddie": collect_eddie_kpi(),
        "cfo": collect_cfo_kpi(),
        "mail": collect_mail_kpi(),
        "approvals": collect_approval_kpi(),
    }


if __name__ == "__main__":
    print(json.dumps(full_status(), indent=2, ensure_ascii=False))
