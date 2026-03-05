---
name: eddie-mail
description: >
  Email automation skill. Fetches Gmail inbox, classifies emails with AI,
  generates reply drafts, and posts to Slack for approval. Use when asked
  about email, inbox, mail processing, or "check my email".
  Also runs via hourly cron job.
user-invocable: true
metadata: {"openclaw": {"emoji": "📬", "requires": {"bins": ["python3"], "env": ["GMAIL_ADDRESS", "GMAIL_APP_PASSWORD", "ANTHROPIC_API_KEY", "SLACK_BOT_TOKEN"]}}}
---

# Eddie Mail - Email Automation

## When to Use
- "Check my email"
- "Process inbox"
- "Any new emails?"
- Heartbeat: check for urgent emails
- Cron: every hour

## Full Pipeline (fetch → classify → draft → post to Slack)
```bash
cd ~/ai-hub && source .venv/bin/activate && python -m src.mail.pipeline
```

## Individual Steps
```bash
# Fetch only
python -m src.mail.fetch

# Classify only
python -m src.mail.classify

# Generate drafts
python -m src.mail.draft

# Post to Slack
python -m src.mail.slack_cards

# Send approved reply
python -m src.mail.send --email-id {id}
```

## Approval Flow
1. Emails appear in #mail-inbox with "Approve & Send" / "Ignore" buttons
2. User clicks Approve → reply is sent via Gmail SMTP
3. Approval history is logged for future auto-approval learning
