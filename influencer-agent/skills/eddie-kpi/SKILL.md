---
name: eddie-kpi
description: >
  Daily and weekly KPI reporting for influencer outreach campaigns. Shows
  discovery stats, outreach metrics, open/reply rates, and pipeline status.
  Use when asked for stats, reports, KPIs, performance, or "how are we doing".
  Runs automatically via daily cron at 9:00 AM.
user-invocable: true
metadata: {"openclaw": {"emoji": "📊", "requires": {"bins": ["python3"], "env": ["SMARTLEAD_API_KEY", "TELEGRAM_BOT_TOKEN"]}}}
---

# Eddie KPI

Generate performance reports for influencer outreach campaigns.

## When to Use
- "Show me today's stats"
- "How are we doing?"
- "KPI report"
- "Weekly summary"
- Daily cron at 9:00 AM JST

## Daily Report
```bash
cd ~/influencer-agent && source .venv/bin/activate && python -m src.kpi.report --type daily --notify
```

## Weekly Report
```bash
python -m src.kpi.report --type weekly --notify
```

## Without Telegram (console only)
```bash
python -m src.kpi.report --type daily
```

## Report Contents
- Discovery: new influencers, total DB count, email extraction rate
- Outreach: emails sent, open rate, reply rate, interested leads
- Pipeline: counts per stage (discovered → contracted)
