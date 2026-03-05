---
name: eddie-followup
description: >
  Email reply monitoring and classification for influencer outreach. Classifies
  replies using Claude, updates lead pipeline status, and sends Telegram alerts
  for interested leads. Use when checking replies, processing responses, or
  managing the influencer pipeline.
  NOT for sending initial outreach or discovering influencers.
user-invocable: true
metadata: {"openclaw": {"emoji": "🔔", "requires": {"bins": ["python3"], "env": ["SMARTLEAD_API_KEY", "ANTHROPIC_API_KEY", "TELEGRAM_BOT_TOKEN"]}}}
---

# Eddie Followup

Monitor and process email replies from influencer outreach.

## When to Use
- "Check for new replies"
- "How are replies looking?"
- "Process new responses"
- "Show me the pipeline"
- During heartbeat checks

## Steps

### Check and Classify New Replies
```bash
cd ~/influencer-agent && source .venv/bin/activate && python -m src.followup.classify --check-new
```

### Send Escalation Notifications
```bash
python -m src.followup.notify --check-escalations
```

### Manual Classification Test
```bash
python -m src.followup.classify --text "message text here"
```

## Reply Categories
- **interested**: Wants to learn more → Telegram alert, move to negotiating
- **meeting_request**: Wants to schedule call → Telegram alert, move to negotiating
- **not_interested**: Declined → Move to rejected, stop sequence
- **question**: Asks questions → Draft suggested response for human
- **out_of_office**: Away → Reschedule followup
- **wrong_person**: Wrong contact → Blacklist

## Heartbeat Integration
This skill should run during heartbeat to check for new replies every 30 minutes.
