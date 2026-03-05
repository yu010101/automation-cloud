#!/usr/bin/env python3
"""Generate personalized outreach emails using Claude API.

Usage:
    python -m src.outreach.personalize --campaign-id 1 --batch-size 50
"""

import argparse
import json
import sys
from pathlib import Path

import anthropic

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from src.shared.config import get_env, load_config
from src.shared.db import get_uncontacted_with_email


SYSTEM_PROMPT = """You are an expert email copywriter for influencer outreach.
Write a personalized cold email to recruit an Instagram influencer to promote a mobile app.

Rules:
- Keep it under 150 words
- Be genuine and specific - reference their content/niche
- Clearly state the CPM compensation offer
- Include a low-friction CTA (quick chat, not a contract)
- Professional but warm tone
- Do NOT use emojis
- Output ONLY the email body (no subject line, no headers)
"""


def generate_email(influencer: dict, config: dict) -> dict:
    """Generate a personalized outreach email for one influencer."""
    client = anthropic.Anthropic(api_key=get_env("ANTHROPIC_API_KEY"))
    outreach_cfg = config.get("outreach", {})

    prompt = f"""Write a personalized cold email to this influencer:

Name: {influencer.get('full_name', influencer['instagram_username'])}
Instagram: @{influencer['instagram_username']}
Bio: {influencer.get('biography', 'N/A')}
Followers: {influencer.get('followers_count', 'N/A')}
Niche: {influencer.get('niche', 'general')}

App details:
- App name: {outreach_cfg.get('app_name', '[APP_NAME]')}
- App URL: {outreach_cfg.get('app_url', '[APP_URL]')}
- CPM rate: ${outreach_cfg.get('cpm_rate', 10)}
- Sender: {outreach_cfg.get('sender_name', '[SENDER]')}
- Company: {outreach_cfg.get('company_name', '[COMPANY]')}
"""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    body = response.content[0].text.strip()
    first_name = influencer.get("full_name", "").split()[0] if influencer.get("full_name") else influencer["instagram_username"]
    subject = f"Partnership opportunity for {first_name}"

    # Append CAN-SPAM required fields
    footer = f"\n\n{outreach_cfg.get('company_name', '[COMPANY]')}\n{outreach_cfg.get('physical_address', '[ADDRESS]')}\n\nUnsubscribe: {outreach_cfg.get('unsubscribe_url', '[UNSUBSCRIBE_URL]')}"
    body += footer

    return {
        "to_email": influencer["email"],
        "to_name": influencer.get("full_name", ""),
        "first_name": first_name,
        "subject": subject,
        "body": body,
        "influencer_id": influencer.get("id"),
        "instagram_username": influencer["instagram_username"],
    }


def generate_batch(campaign_id: int, batch_size: int = 50) -> list[dict]:
    """Generate personalized emails for a batch of uncontacted influencers."""
    config = load_config()
    influencers = get_uncontacted_with_email(limit=batch_size)

    if not influencers:
        print("No uncontacted influencers with email found.")
        return []

    print(f"Generating personalized emails for {len(influencers)} influencers...")
    emails = []
    for i, inf in enumerate(influencers, 1):
        print(f"  [{i}/{len(influencers)}] @{inf['instagram_username']}...")
        email = generate_email(inf, config)
        email["campaign_id"] = campaign_id
        emails.append(email)

    return emails


def main():
    parser = argparse.ArgumentParser(description="Generate personalized outreach emails")
    parser.add_argument("--campaign-id", type=int, required=True)
    parser.add_argument("--batch-size", type=int, default=50)
    args = parser.parse_args()

    emails = generate_batch(args.campaign_id, args.batch_size)
    print(json.dumps({"generated": len(emails), "emails": [{"to": e["to_email"], "subject": e["subject"]} for e in emails]}, indent=2))


if __name__ == "__main__":
    main()
