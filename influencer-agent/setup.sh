#!/bin/bash
# Eddie Influencer Agent - Setup Script
set -e

PROJECT_DIR="$HOME/influencer-agent"
cd "$PROJECT_DIR"

echo "=== Eddie Influencer Agent Setup ==="
echo ""

# 1. Python venv
echo "[1/5] Setting up Python virtual environment..."
python3 -m venv .venv
source .venv/bin/activate
pip install -q -r requirements.txt
echo "  Done."

# 2. Environment variables
echo ""
echo "[2/5] Checking environment..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "  Created .env from template. Please edit with your API keys:"
    echo "    - APIFY_API_TOKEN"
    echo "    - SMARTLEAD_API_KEY"
    echo "    - ANTHROPIC_API_KEY"
    echo "    - TELEGRAM_BOT_TOKEN"
    echo "    - TELEGRAM_CHAT_ID"
else
    echo "  .env already exists."
fi

# 3. Initialize database
echo ""
echo "[3/5] Initializing database..."
python3 -c "from src.shared.db import init_db; init_db()"
echo "  Database initialized at data/influencer_agent.db"

# 4. Link OpenClaw skills
echo ""
echo "[4/5] Linking OpenClaw skills..."
OPENCLAW_SKILLS="$HOME/.openclaw/skills"
if [ -d "$OPENCLAW_SKILLS" ]; then
    for skill in eddie-discover eddie-outreach eddie-followup eddie-kpi; do
        if [ ! -L "$OPENCLAW_SKILLS/$skill" ]; then
            ln -s "$PROJECT_DIR/skills/$skill" "$OPENCLAW_SKILLS/$skill"
            echo "  Linked: $skill"
        else
            echo "  Already linked: $skill"
        fi
    done
else
    echo "  WARNING: OpenClaw skills directory not found at $OPENCLAW_SKILLS"
    echo "  Please manually link skills after OpenClaw setup."
fi

# 5. Config reminder
echo ""
echo "[5/5] Configuration..."
echo "  Edit config.yaml with your app details:"
echo "    - discovery.niche_keywords"
echo "    - discovery.hashtags"
echo "    - outreach.app_name / app_url"
echo "    - outreach.sender_name / company_name"
echo "    - outreach.physical_address (CAN-SPAM required)"
echo ""
echo "=== Setup complete! ==="
echo ""
echo "Quick start:"
echo "  cd ~/influencer-agent && source .venv/bin/activate"
echo "  python -m src.discovery.search --niche 'fitness' --hashtags 'fitnessmotivation' --limit 50"
echo ""
echo "Or via OpenClaw:"
echo "  /eddie-discover niche:fitness hashtags:fitnessmotivation"
