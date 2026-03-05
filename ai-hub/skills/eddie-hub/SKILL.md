---
name: eddie-hub
description: >
  Unified daily briefing and project status hub. Collects KPIs from Eddie
  (influencer), CFO Agent, mail processing, and approval queue into a single
  Slack report. Use when asked for status, briefing, overview, or "how are
  we doing across everything".
user-invocable: true
metadata: {"openclaw": {"emoji": "📋", "requires": {"bins": ["python3"], "env": ["SLACK_BOT_TOKEN"]}}}
---

# Eddie Hub - Unified Status

## When to Use
- "How are we doing?"
- "Daily briefing"
- "Project status"
- "Show me everything"
- Cron: every morning at 9:00 AM JST

## Post to Slack
```bash
cd ~/ai-hub && source .venv/bin/activate && python -m src.hub.briefing --post
```

## Console Only
```bash
cd ~/ai-hub && source .venv/bin/activate && python -m src.hub.briefing
```

## Full Status JSON
```bash
cd ~/ai-hub && source .venv/bin/activate && python -m src.hub.status
```
