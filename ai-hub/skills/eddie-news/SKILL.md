---
name: eddie-news
description: >
  News collection and summarization skill. Fetches RSS/Atom feeds,
  stores articles, and generates AI-powered news digests.
  Integrated into the daily briefing automatically.
user-invocable: true
metadata: {"openclaw": {"emoji": "📰", "requires": {"bins": ["python3"], "env": ["ANTHROPIC_API_KEY"]}}}
---

# Eddie News - RSS/News Collection & Summarization

## When to Use
- "What's in the news?"
- "Tech news today"
- "Fetch latest news"
- "News digest"
- Automatic: runs before daily briefing

## Full Pipeline (fetch → summarize)
```bash
cd ~/ai-hub && source .venv/bin/activate && python -m src.news.pipeline
```

## Individual Steps
```bash
# Fetch RSS feeds only
python -m src.news.fetch

# Generate summary only
python -m src.news.summarize
```

## Post to Slack
```bash
python -m src.news.pipeline --post
```

## Configure Feeds
Edit `~/ai-hub/config.yaml` under the `news:` section to add/remove RSS feeds.
