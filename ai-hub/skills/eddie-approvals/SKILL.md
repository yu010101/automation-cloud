---
name: eddie-approvals
description: >
  Cross-project approval flow manager. Shows pending approvals from all
  projects (mail, influencer, CFO), handles approve/reject via Slack,
  and learns patterns for auto-approval. Use when asked about approvals,
  pending items, or "what needs my attention".
user-invocable: true
metadata: {"openclaw": {"emoji": "✅", "requires": {"bins": ["python3"], "env": ["SLACK_BOT_TOKEN"]}}}
---

# Eddie Approvals - Approval Flow Manager

## When to Use
- "What needs approval?"
- "Show pending items"
- "Approve all"
- "Auto-approval report"
- "What needs my attention?"

## List Pending
```bash
cd ~/ai-hub && source .venv/bin/activate && python -m src.kpi.approval --action list
```

## Post to Slack
```bash
python -m src.kpi.slack_approvals
```

## Approve/Reject via CLI
```bash
python -m src.kpi.approval --action approve --id {id}
python -m src.kpi.approval --action reject --id {id} --reason "reason"
```

## Auto-Approval Report
```bash
python -m src.kpi.auto_approve --report
```

## Suggest Auto-Approval Candidates
```bash
python -m src.kpi.auto_approve --suggest
```

## Enable Auto-Approval
```bash
python -m src.kpi.auto_approve --enable-pattern {hash}
```
