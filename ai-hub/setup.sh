#!/bin/bash
# AI Hub - Setup Script
set -e

PROJECT_DIR="$HOME/ai-hub"
cd "$PROJECT_DIR"

echo "=== AI Hub Setup ==="
echo ""

# 1. Python venv
echo "[1/5] Python environment..."
python3 -m venv .venv
source .venv/bin/activate
pip install -q -r requirements.txt
echo "  Done."

# 2. .env
echo ""
echo "[2/5] Environment..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "  Created .env - please configure API keys."
else
    echo "  .env exists."
fi

# 3. Database
echo ""
echo "[3/5] Database..."
python3 -c "from src.shared.db import init_db; init_db()"
echo "  Initialized data/hub.db"

# 4. OpenClaw Skills
echo ""
echo "[4/5] OpenClaw skills..."
OPENCLAW_SKILLS="$HOME/.openclaw/skills"
if [ -d "$OPENCLAW_SKILLS" ]; then
    for skill in eddie-hub eddie-mail eddie-approvals; do
        if [ ! -L "$OPENCLAW_SKILLS/$skill" ]; then
            ln -s "$PROJECT_DIR/skills/$skill" "$OPENCLAW_SKILLS/$skill"
            echo "  Linked: $skill"
        else
            echo "  Already linked: $skill"
        fi
    done
else
    echo "  WARNING: OpenClaw skills dir not found"
fi

# 5. HEARTBEAT.md
echo ""
echo "[5/5] HEARTBEAT configuration..."
HEARTBEAT="$HOME/.openclaw/workspace/HEARTBEAT.md"
if [ -f "$HEARTBEAT" ]; then
    # Check if our entries already exist
    if ! grep -q "ai-hub" "$HEARTBEAT" 2>/dev/null; then
        cat >> "$HEARTBEAT" << 'HEARTBEAT_EOF'

## AI Hub Checks
- Check for urgent unprocessed emails: run `cd ~/ai-hub && source .venv/bin/activate && python -m src.mail.pipeline` if new emails need processing
- Check pending approvals: run `cd ~/ai-hub && source .venv/bin/activate && python -m src.kpi.slack_approvals` if there are unposted approvals
- If nothing needs attention, respond HEARTBEAT_OK
HEARTBEAT_EOF
        echo "  Updated HEARTBEAT.md"
    else
        echo "  HEARTBEAT.md already configured"
    fi
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "  1. Edit .env with your API keys"
echo "  2. Edit config.yaml with Slack channel IDs"
echo "  3. Test: cd ~/ai-hub && source .venv/bin/activate"
echo "     python -m src.hub.briefing          # Console briefing"
echo "     python -m src.mail.pipeline          # Email pipeline"
echo "     python -m src.kpi.approval --action stats  # Approval stats"
echo ""
echo "OpenClaw commands:"
echo "  /eddie-hub         # Daily briefing"
echo "  /eddie-mail        # Process emails"
echo "  /eddie-approvals   # Manage approvals"
