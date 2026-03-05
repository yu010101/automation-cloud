# automation-cloud セットアップガイド

## 前提条件

- GitHub アカウント
- Turso CLI (`brew install tursodatabase/tap/turso`)
- Cloudflare アカウント + Wrangler CLI (`npm i -g wrangler`)
- Node.js 18+

## Step 1: Turso DB 作成

```bash
turso auth signup  # or turso auth login
turso db create hub-db --location nrt
turso db create eddie-db --location nrt

# トークン取得
turso db tokens create hub-db
turso db tokens create eddie-db

# URL確認
turso db show hub-db --url
turso db show eddie-db --url
```

## Step 2: ローカルDBをTursoに移行

```bash
cd ~/automation-cloud
pip install libsql-experimental

export TURSO_HUB_URL="libsql://hub-db-xxx.turso.io"
export TURSO_HUB_TOKEN="eyJ..."
export TURSO_EDDIE_URL="libsql://eddie-db-xxx.turso.io"
export TURSO_EDDIE_TOKEN="eyJ..."

python scripts/migrate-to-turso.py --hub --eddie

# 確認
turso db shell hub-db "SELECT COUNT(*) FROM emails"
turso db shell eddie-db "SELECT COUNT(*) FROM influencers"
```

## Step 3: GitHub リポジトリ + Secrets

```bash
cd ~/automation-cloud
gh repo create yu01/automation-cloud --private --push --source .

# Secrets 登録 (対話形式)
gh secret set ANTHROPIC_API_KEY
gh secret set SLACK_BOT_TOKEN
gh secret set SLACK_CHANNEL_BRIEFING
gh secret set SLACK_CHANNEL_MAIL
gh secret set SLACK_CHANNEL_APPROVALS
gh secret set GMAIL_ADDRESS
gh secret set GMAIL_APP_PASSWORD
gh secret set TELEGRAM_BOT_TOKEN
gh secret set TELEGRAM_CHAT_ID
gh secret set TURSO_HUB_URL
gh secret set TURSO_HUB_TOKEN
gh secret set TURSO_EDDIE_URL
gh secret set TURSO_EDDIE_TOKEN
gh secret set CFO_API_URL
```

## Step 4: GitHub Actions テスト

```bash
# 各ワークフローを手動実行
gh workflow run news-fetch.yml
gh workflow run morning-brief.yml
gh workflow run hub-briefing.yml
gh workflow run mail-check.yml
gh workflow run kpi-collect.yml
gh workflow run approval-weekly.yml

# 結果確認
gh run list
```

## Step 5: Cloudflare Worker デプロイ

```bash
cd webhook-worker
npm install
wrangler login

# Secrets 設定
wrangler secret put ANTHROPIC_API_KEY
wrangler secret put TURSO_EDDIE_URL
wrangler secret put TURSO_EDDIE_TOKEN
wrangler secret put TELEGRAM_BOT_TOKEN
wrangler secret put TELEGRAM_CHAT_ID

# デプロイ
wrangler deploy

# テスト
curl -X POST https://eddie-webhook.YOUR_SUBDOMAIN.workers.dev/webhook/smartlead \
  -H "Content-Type: application/json" \
  -d '{"event_type":"EMAIL_REPLY","sl_lead_email":"test@example.com","preview_text":"Thanks, Im interested!"}'
```

## Step 6: Smartlead Webhook URL 更新

Smartlead ダッシュボードで webhook URL を更新:
`https://eddie-webhook.YOUR_SUBDOMAIN.workers.dev/webhook/smartlead`

## Step 7: ローカル環境をTursoに接続

```bash
# ~/ai-hub/.env に追加
DB_BACKEND=turso
TURSO_HUB_URL=libsql://hub-db-xxx.turso.io
TURSO_HUB_TOKEN=eyJ...

# ~/influencer-agent/.env に追加
DB_BACKEND=turso
TURSO_EDDIE_URL=libsql://eddie-db-xxx.turso.io
TURSO_EDDIE_TOKEN=eyJ...
```

## 月額コスト: $0

| サービス | 無料枠 | 想定使用量 |
|---------|--------|-----------|
| GitHub Actions | 2,000分/月 | ~844分 |
| Turso | 9GB, 25B reads | 2DB, <100MB |
| Cloudflare Workers | 100K req/日 | ~100 req/日 |
