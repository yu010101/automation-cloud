# 設計書: インフルエンサー採用自動化システム

## 1. システムアーキテクチャ

### 全体構成

```
┌─────────────────── OpenClaw Gateway ───────────────────┐
│                                                         │
│  Heartbeat (30min)     Cron (daily 9:00 JST)           │
│      │                      │                          │
│      ▼                      ▼                          │
│  ┌─────────┐          ┌─────────┐                      │
│  │HEARTBEAT│          │eddie-kpi│                       │
│  │  .md    │          │  Skill  │                       │
│  └─────────┘          └─────────┘                      │
│                                                         │
│  User Commands (Telegram/Discord):                      │
│                                                         │
│  /eddie-discover     → Discovery Skill                  │
│  /eddie-outreach     → Outreach Skill                   │
│  /eddie-followup     → Followup Skill                   │
│  /eddie-kpi          → KPI Skill                        │
│  /eddie-dm           → DM Skill (optional)              │
│                                                         │
└────────────────────────┬────────────────────────────────┘
                         │ exec tool
                         ▼
┌──────────── Python Scripts Layer ──────────────────────┐
│                                                         │
│  src/                                                   │
│  ├── discovery/                                         │
│  │   ├── search.py      ← Apify Instagram Scraper      │
│  │   ├── filter.py      ← フォロワー/再生数フィルタ     │
│  │   └── extract.py     ← メール抽出 (regex + website)  │
│  │                                                      │
│  ├── outreach/                                          │
│  │   ├── personalize.py ← Claude API メール生成         │
│  │   ├── campaign.py    ← Smartlead キャンペーン管理    │
│  │   └── send.py        ← Smartlead リード追加          │
│  │                                                      │
│  ├── followup/                                          │
│  │   ├── webhook.py     ← Smartlead Webhook受信サーバ   │
│  │   ├── classify.py    ← Claude API 返信分類           │
│  │   └── notify.py      ← Telegram通知                  │
│  │                                                      │
│  ├── kpi/                                               │
│  │   └── report.py      ← 集計・レポート生成            │
│  │                                                      │
│  ├── dm/                (optional)                      │
│  │   └── dm.py          ← instagrapi DM送信             │
│  │                                                      │
│  └── shared/                                            │
│      ├── config.py      ← YAML設定読み込み              │
│      ├── db.py          ← SQLite操作                    │
│      └── models.py      ← データモデル定義              │
│                                                         │
└────────────────────────┬────────────────────────────────┘
                         │
          ┌──────────────┼──────────────────┐
          ▼              ▼                  ▼
   ┌───────────┐  ┌───────────┐     ┌───────────┐
   │   Apify   │  │ Smartlead │     │  Claude   │
   │  API      │  │  API      │     │  API      │
   └───────────┘  └───────────┘     └───────────┘
                                    ┌───────────┐
                                    │ Telegram  │
                                    │  Bot API  │
                                    └───────────┘
```

### データフロー

```
1. DISCOVER:
   User/Cron → eddie-discover → search.py (Apify) → filter.py → extract.py → SQLite

2. OUTREACH:
   User/Cron → eddie-outreach → personalize.py (Claude) → campaign.py (Smartlead) → send.py → SQLite

3. FOLLOWUP:
   Smartlead Webhook → webhook.py → classify.py (Claude) → notify.py (Telegram) → SQLite

4. KPI:
   Cron (daily) → eddie-kpi → report.py (SQLite + Smartlead stats) → Telegram
```

---

## 2. データモデル（SQLite）

### テーブル設計

```sql
-- インフルエンサー情報
CREATE TABLE influencers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    instagram_username TEXT UNIQUE NOT NULL,
    full_name TEXT,
    biography TEXT,
    followers_count INTEGER,
    avg_views INTEGER,
    avg_engagement_rate REAL,
    email TEXT,
    email_source TEXT,  -- 'bio' | 'website' | 'business_contact'
    website_url TEXT,
    niche TEXT,
    is_verified BOOLEAN DEFAULT FALSE,
    is_business_account BOOLEAN DEFAULT FALSE,
    status TEXT DEFAULT 'discovered',
    -- status: discovered → contacted → replied → negotiating → contracted → rejected → blacklisted
    discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    contacted_at TIMESTAMP,
    replied_at TIMESTAMP,
    notes TEXT,
    raw_data JSON  -- Apify生データ保存
);

-- アウトリーチキャンペーン
CREATE TABLE campaigns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    smartlead_campaign_id INTEGER,
    name TEXT NOT NULL,
    niche TEXT,
    template_name TEXT,
    status TEXT DEFAULT 'drafted',  -- drafted | active | paused | completed
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    config JSON  -- CPM rate, follow-up schedule etc.
);

-- メール送信ログ
CREATE TABLE outreach_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    influencer_id INTEGER REFERENCES influencers(id),
    campaign_id INTEGER REFERENCES campaigns(id),
    smartlead_lead_id INTEGER,
    email_sent_at TIMESTAMP,
    sequence_number INTEGER DEFAULT 1,
    email_subject TEXT,
    email_body TEXT,
    status TEXT DEFAULT 'pending',  -- pending | sent | opened | clicked | replied | bounced | unsubscribed
    reply_text TEXT,
    reply_category TEXT,  -- interested | meeting_request | not_interested | question | out_of_office | wrong_person
    reply_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- DM送信ログ (optional)
CREATE TABLE dm_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    influencer_id INTEGER REFERENCES influencers(id),
    dm_text TEXT,
    sent_at TIMESTAMP,
    status TEXT DEFAULT 'sent',  -- sent | read | replied | failed
    reply_text TEXT,
    reply_at TIMESTAMP
);

-- 日次KPI
CREATE TABLE daily_kpi (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE UNIQUE NOT NULL,
    influencers_discovered INTEGER DEFAULT 0,
    emails_sent INTEGER DEFAULT 0,
    emails_opened INTEGER DEFAULT 0,
    emails_replied INTEGER DEFAULT 0,
    dms_sent INTEGER DEFAULT 0,
    leads_interested INTEGER DEFAULT 0,
    leads_contracted INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- インデックス
CREATE INDEX idx_influencers_status ON influencers(status);
CREATE INDEX idx_influencers_email ON influencers(email);
CREATE INDEX idx_influencers_username ON influencers(instagram_username);
CREATE INDEX idx_outreach_status ON outreach_logs(status);
CREATE INDEX idx_daily_kpi_date ON daily_kpi(date);
```

---

## 3. 設定ファイル（config.yaml）

```yaml
# ~/influencer-agent/config.yaml

# --- 検索条件 ---
discovery:
  niche_keywords:
    - ""  # ユーザーが設定
  hashtags:
    - ""  # ユーザーが設定
  filters:
    min_followers: 10000
    max_followers: 50000
    min_avg_views: 10000
    min_engagement_rate: 0.02  # 2%
    must_have_email: false     # true にするとメールありのみ
    exclude_verified: false
  max_results_per_search: 200
  search_interval_hours: 24   # 検索実行間隔

# --- メールアウトリーチ ---
outreach:
  daily_email_limit: 1000
  emails_per_batch: 100       # Smartlead API制限
  cpm_rate: 10                # $10 CPM提案デフォルト
  app_name: ""                # ユーザーが設定
  app_url: ""
  sender_name: ""
  company_name: ""
  physical_address: ""        # CAN-SPAM必須
  unsubscribe_url: ""
  follow_up_sequence:
    - delay_days: 3
      template: "followup_1"
    - delay_days: 7
      template: "followup_2"
    - delay_days: 14
      template: "followup_3"
    - delay_days: 21
      template: "breakup"

# --- DM設定 (optional) ---
dm:
  enabled: false
  daily_limit: 100
  delay_between_dms_sec: 120  # 2分間隔
  warmup_days: 14
  warmup_daily_start: 10

# --- 通知 ---
notifications:
  telegram:
    bot_token: ""  # 環境変数 TELEGRAM_BOT_TOKEN
    chat_id: ""    # 環境変数 TELEGRAM_CHAT_ID
  escalation_triggers:
    - "interested"
    - "meeting_request"

# --- KPIレポート ---
kpi:
  daily_report_cron: "0 9 * * *"   # 毎日9:00
  weekly_report_cron: "0 9 * * 1"  # 毎週月曜9:00
  timezone: "Asia/Tokyo"

# --- データベース ---
database:
  path: "data/influencer_agent.db"
```

---

## 4. OpenClaw Skill設計

### 4.1 eddie-discover

```yaml
---
name: eddie-discover
description: >
  Instagram influencer discovery skill. Searches for influencers matching
  specified criteria (followers, views, niche) using Apify Instagram Scraper.
  Extracts emails from bios and linked websites. Use when the user asks to
  find influencers, search for creators, or discover new leads.
  NOT for sending emails or DMs.
user-invocable: true
metadata: {"openclaw": {"emoji": "🔍", "requires": {"bins": ["python3"], "env": ["APIFY_API_TOKEN"]}}}
---

# Eddie Discover - Influencer Discovery

## When to Use
- User asks to find/discover/search for influencers
- Scheduled via cron for periodic discovery runs
- User asks to refresh or update the influencer database

## Parameters
The user can specify:
- `niche`: Target niche/keywords (e.g., "fitness", "christian", "study")
- `hashtags`: Instagram hashtags to search
- `min_followers` / `max_followers`: Follower range (default: 10K-50K)
- `min_views`: Minimum average views (default: 10K)
- `limit`: Max results to fetch (default: 200)

## Execution Steps

1. Read config from `~/influencer-agent/config.yaml`
2. Run the discovery script:
   ```
   python3 ~/influencer-agent/src/discovery/search.py \
     --niche "{niche}" \
     --hashtags "{hashtags}" \
     --min-followers {min_followers} \
     --max-followers {max_followers} \
     --min-views {min_views} \
     --limit {limit}
   ```
3. The script will:
   - Search Instagram via Apify
   - Filter by follower count and engagement
   - Extract emails from bios
   - Save to SQLite database
   - Output a summary JSON

4. Report results to user:
   - Total profiles found
   - Profiles matching criteria
   - Profiles with emails
   - Top 5 matches by engagement rate

## Output Format
```
Discovery Results:
- Searched: {N} profiles
- Matched criteria: {M} profiles
- With email: {E} profiles
- New (not in DB): {K} profiles
- Top matches: [list of usernames with stats]
```
```

### 4.2 eddie-outreach

```yaml
---
name: eddie-outreach
description: >
  Email outreach skill for influencer recruitment. Generates personalized
  cold emails using Claude API and sends them via Smartlead campaigns.
  Use when the user asks to reach out to influencers, send emails,
  start a campaign, or contact creators.
  NOT for DM sending or influencer discovery.
user-invocable: true
metadata: {"openclaw": {"emoji": "📧", "requires": {"bins": ["python3"], "env": ["SMARTLEAD_API_KEY", "ANTHROPIC_API_KEY"]}}}
---

# Eddie Outreach - Email Campaign Manager

## When to Use
- User asks to send emails to discovered influencers
- User asks to start/create a new outreach campaign
- User asks to personalize emails for specific influencers
- Scheduled via cron for daily outreach batches

## Parameters
- `campaign_name`: Name for the Smartlead campaign
- `niche`: Target niche (for email personalization context)
- `batch_size`: Number of influencers to contact (default: from config)
- `template`: Email template to use (default: "initial_outreach")

## Execution Steps

1. Read config and fetch un-contacted influencers from DB:
   ```
   python3 ~/influencer-agent/src/outreach/campaign.py \
     --action create \
     --name "{campaign_name}" \
     --niche "{niche}"
   ```

2. Generate personalized emails:
   ```
   python3 ~/influencer-agent/src/outreach/personalize.py \
     --campaign-id {id} \
     --batch-size {batch_size} \
     --template "{template}"
   ```

3. Upload leads and activate campaign:
   ```
   python3 ~/influencer-agent/src/outreach/send.py \
     --campaign-id {id} \
     --activate
   ```

4. Report results

## Email Templates

### initial_outreach
Subject: Partnership opportunity for {first_name}

Hi {first_name},

I've been following your content on Instagram and really enjoyed
your recent posts about {niche_topic}. Your engagement with your
audience stands out.

I'm {sender_name} from {company_name}. We built {app_name}
({app_url}) and we're looking to partner with creators like you.

Here's what we offer:
- ${cpm_rate} CPM compensation
- Full creative freedom
- Free premium access to the app

Would you be open to a quick chat? Happy to share more details.

Best,
{sender_name}
{company_name}
{physical_address}

[Unsubscribe]({unsubscribe_url})

### followup_1 (3 days later)
Subject: Re: Partnership opportunity for {first_name}

### followup_2 (7 days later)
Subject: Quick update for {first_name}

### breakup (21 days later)
Subject: Last note from {sender_name}
```

### 4.3 eddie-followup

```yaml
---
name: eddie-followup
description: >
  Monitors email replies from influencer outreach campaigns via Smartlead
  webhooks. Classifies replies using Claude API and escalates interested
  leads to Telegram. Use when checking reply status, processing responses,
  or managing the lead pipeline.
  NOT for sending initial emails or discovering influencers.
user-invocable: true
metadata: {"openclaw": {"emoji": "🔔", "requires": {"bins": ["python3"], "env": ["SMARTLEAD_API_KEY", "ANTHROPIC_API_KEY", "TELEGRAM_BOT_TOKEN"]}}}
---

# Eddie Followup - Reply Management

## When to Use
- Heartbeat check: scan for new replies
- User asks about reply status or pipeline
- User asks to process/classify new replies
- Webhook triggers (automated)

## Execution Steps

1. Check for new replies:
   ```
   python3 ~/influencer-agent/src/followup/classify.py --check-new
   ```

2. For each new reply, Claude classifies into:
   - `interested` → Telegram alert + status update
   - `meeting_request` → Telegram alert + status update
   - `not_interested` → Log + pause sequence
   - `question` → Draft suggested response for human review
   - `out_of_office` → Reschedule followup
   - `wrong_person` → Blacklist

3. Send notifications:
   ```
   python3 ~/influencer-agent/src/followup/notify.py
   ```

## Heartbeat Integration
Add to HEARTBEAT.md:
```
- Check for new influencer email replies and process them
```
```

### 4.4 eddie-kpi

```yaml
---
name: eddie-kpi
description: >
  Daily KPI reporting for influencer outreach campaigns. Aggregates
  data from SQLite and Smartlead to produce actionable reports.
  Use when the user asks for stats, reports, KPIs, or campaign performance.
  Runs automatically via daily cron job.
user-invocable: true
metadata: {"openclaw": {"emoji": "📊", "requires": {"bins": ["python3"], "env": ["SMARTLEAD_API_KEY", "TELEGRAM_BOT_TOKEN"]}}}
---

# Eddie KPI - Daily Performance Reporter

## When to Use
- Daily cron at 9:00 AM JST
- User asks for campaign stats, KPIs, or performance
- User asks "how are we doing?"

## Report Contents

### Daily Report
```
📊 Daily KPI Report - {date}
━━━━━━━━━━━━━━━━━━━━━
Discovery:
  New influencers found: {N}
  Total in database: {N}
  With email: {N}

Outreach:
  Emails sent today: {N}
  Open rate: {N}%
  Reply rate: {N}%
  Interested leads: {N}

Pipeline:
  Discovered: {N}
  Contacted: {N}
  Replied: {N}
  Negotiating: {N}
  Contracted: {N}

Cost:
  Apify: ${N}
  Smartlead: ${N}
  Claude API: ${N}
  Estimated total: ${N}
━━━━━━━━━━━━━━━━━━━━━
```

## Execution
```
python3 ~/influencer-agent/src/kpi/report.py --type daily
python3 ~/influencer-agent/src/kpi/report.py --type weekly
```
```

---

## 5. Webhook受信サーバ設計

```
# Smartlead Webhook → Local Server → SQLite + Telegram

Webhook URL: https://{your-domain}/webhook/smartlead
(ngrok or Cloudflare Tunnel for local development)

Events to subscribe:
- EMAIL_REPLY
- EMAIL_BOUNCE
- LEAD_UNSUBSCRIBED
- LEAD_CATEGORY_UPDATED

Server: FastAPI (lightweight, async)
Port: 8765
```

---

## 6. ファイル構成（最終）

```
~/influencer-agent/
├── config.yaml                    # メイン設定ファイル
├── .env                           # APIキー（gitignore対象）
├── data/
│   └── influencer_agent.db        # SQLiteデータベース
├── docs/
│   ├── requirements/
│   │   └── influencer-automation.md
│   ├── specs/
│   │   └── influencer-automation.md  # ← このファイル
│   └── api/
│       └── influencer-automation.yaml
├── src/
│   ├── __init__.py
│   ├── discovery/
│   │   ├── __init__.py
│   │   ├── search.py              # Apify Instagram検索
│   │   ├── filter.py              # フィルタリングロジック
│   │   └── extract.py             # メール抽出
│   ├── outreach/
│   │   ├── __init__.py
│   │   ├── personalize.py         # Claude APIメール生成
│   │   ├── campaign.py            # Smartleadキャンペーン管理
│   │   └── send.py                # リード追加・送信
│   ├── followup/
│   │   ├── __init__.py
│   │   ├── webhook_server.py      # FastAPI Webhookサーバ
│   │   ├── classify.py            # Claude API返信分類
│   │   └── notify.py              # Telegram通知
│   ├── kpi/
│   │   ├── __init__.py
│   │   └── report.py              # KPIレポート生成
│   ├── dm/                        # (optional)
│   │   ├── __init__.py
│   │   └── dm.py                  # instagrapi DM
│   └── shared/
│       ├── __init__.py
│       ├── config.py              # YAML設定読み込み
│       ├── db.py                  # SQLite操作
│       └── models.py              # データクラス定義
├── skills/                        # OpenClaw Skills (symlink先)
│   ├── eddie-discover/
│   │   └── SKILL.md
│   ├── eddie-outreach/
│   │   └── SKILL.md
│   ├── eddie-followup/
│   │   └── SKILL.md
│   ├── eddie-kpi/
│   │   └── SKILL.md
│   └── eddie-dm/                  # (optional)
│       └── SKILL.md
├── templates/                     # メールテンプレート
│   ├── initial_outreach.txt
│   ├── followup_1.txt
│   ├── followup_2.txt
│   ├── followup_3.txt
│   └── breakup.txt
├── tasks/
│   ├── todo.md
│   └── lessons.md
├── tests/
│   ├── test_discovery.py
│   ├── test_outreach.py
│   └── test_classify.py
├── requirements.txt
├── pyproject.toml
└── .gitignore
```

---

## 7. セットアップ手順（概要）

### 前提条件
1. OpenClaw インストール済み ✅
2. Python 3.11+ インストール済み
3. Apify アカウント（$29/mo Starter）
4. Smartlead アカウント（$94/mo Pro）
5. Claude API キー（Anthropic）
6. Telegram Bot（@BotFatherで作成）
7. 10-12個のメールドメイン + Google Workspace

### インストール手順
```bash
cd ~/influencer-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# .envファイルを設定
cp .env.example .env
# → APIキーを入力

# データベース初期化
python3 -c "from src.shared.db import init_db; init_db()"

# OpenClaw Skills をリンク
ln -s ~/influencer-agent/skills/eddie-discover ~/.openclaw/skills/eddie-discover
ln -s ~/influencer-agent/skills/eddie-outreach ~/.openclaw/skills/eddie-outreach
ln -s ~/influencer-agent/skills/eddie-followup ~/.openclaw/skills/eddie-followup
ln -s ~/influencer-agent/skills/eddie-kpi ~/.openclaw/skills/eddie-kpi
```
