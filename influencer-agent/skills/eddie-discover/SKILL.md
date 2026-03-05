---
name: eddie-discover
description: >
  Instagram influencer discovery and lead generation. Searches for micro-influencers
  matching criteria (follower count, views, niche) using Apify Instagram Scraper.
  Extracts emails from bios. Use when asked to find influencers, search for creators,
  discover leads, or refresh the influencer database.
  NOT for sending emails, DMs, or managing campaigns.
user-invocable: true
metadata: {"openclaw": {"emoji": "🔍", "requires": {"bins": ["python3"], "env": ["APIFY_API_TOKEN"]}}}
---

# Eddie Discover

Find Instagram influencers matching your criteria and extract contact info.

## When to Use
- "Find influencers in {niche}"
- "Search for creators"
- "Discover new leads"
- "Refresh influencer database"
- Periodic discovery via cron

## Parameters (from user message)
Extract these from the user's request:
- `niche`: Target niche keywords (e.g., "fitness", "christian")
- `hashtags`: Instagram hashtags to search (comma-separated)
- `min_followers`: Minimum followers (default: 10000)
- `max_followers`: Maximum followers (default: 50000)
- `min_views`: Minimum average views (default: 10000)
- `limit`: Max profiles to fetch (default: 200)

If usernames are specified directly, use `--usernames` instead.

## Steps

1. Activate the Python environment and run discovery:

```bash
cd ~/influencer-agent && source .venv/bin/activate && python -m src.discovery.search \
  --niche "{niche}" \
  --hashtags "{hashtags}" \
  --min-followers {min_followers} \
  --max-followers {max_followers} \
  --min-views {min_views} \
  --limit {limit}
```

2. Parse the JSON output and present a summary:
   - Total profiles searched
   - Profiles matching criteria
   - Profiles with email addresses
   - Top 5 matches by engagement rate

3. Ask user if they want to proceed to outreach with `/eddie-outreach`.
