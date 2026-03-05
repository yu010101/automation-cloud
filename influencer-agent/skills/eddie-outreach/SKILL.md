---
name: eddie-outreach
description: >
  Email outreach campaign manager for influencer recruitment. Creates Smartlead
  campaigns, generates personalized cold emails with Claude, and uploads leads.
  Use when asked to contact influencers, send outreach emails, start a campaign,
  or reach out to creators.
  NOT for discovering influencers or sending DMs.
user-invocable: true
metadata: {"openclaw": {"emoji": "📧", "requires": {"bins": ["python3"], "env": ["SMARTLEAD_API_KEY", "ANTHROPIC_API_KEY"]}}}
---

# Eddie Outreach

Send personalized outreach emails to discovered influencers via Smartlead.

## When to Use
- "Send emails to influencers"
- "Start outreach campaign"
- "Contact the discovered creators"
- "Create a new campaign for {niche}"

## Parameters
- `campaign_name`: Name for the campaign (default: "{niche} Outreach - {date}")
- `niche`: Target niche for personalization context
- `batch_size`: Number of influencers to contact (default: 100)

## Steps

### Step 1: Create Campaign
```bash
cd ~/influencer-agent && source .venv/bin/activate && python -m src.outreach.campaign \
  --action create --name "{campaign_name}" --niche "{niche}"
```
Save the returned `local_id` for next steps.

### Step 2: Generate and Send
```bash
python -m src.outreach.send \
  --campaign-id {local_id} --batch-size {batch_size} --activate
```

### Step 3: Report
Present the results:
- Emails generated and uploaded
- Campaign activated status
- Any duplicates or invalid emails skipped

### Checking Status
```bash
python -m src.outreach.campaign --action status --campaign-id {smartlead_id}
```
