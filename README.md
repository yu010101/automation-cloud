# automation-cloud

> 業務自動化エージェントの monorepo。LLM（Claude）と Slack / メール / Web を結び、日次オペレーションを無人で回す Python エージェント群。

2 つの独立エージェントを同梱する。いずれも `config.yaml` 駆動・cron 運用前提で、`src/` にドメイン別モジュール、`skills/` `tasks/` `tests/` `docs/` を持つ共通構成。

| エージェント | 役割 |
|---|---|
| **ai-hub** | 日次ブリーフィング・KPI 収集／承認・メール仕分け＆下書き・ニュース要約を Slack に集約する「経営オペレーションのハブ」 |
| **influencer-agent**（Eddie） | インフルエンサーの発見 → パーソナライズ・アウトリーチ → 返信フォロー → KPI までを回す B2C アウトリーチ自動化 |

## ai-hub

毎朝のブリーフィングを軸に、メール・KPI・ニュースを集約して Slack に届ける。

```
  メール(IMAP) ─► mail/ (fetch → classify → draft → send, Slack cards)
  KPI ──────────► kpi/  (collector → approval / auto_approve → Slack 承認)
  ニュース ──────► news/ (fetch → summarize)
        └─────────► hub/  (briefing → Slack #daily-briefing, status)
```

| モジュール | 内容 |
|---|---|
| `src/hub/` | 日次ブリーフィング生成（`briefing`）・稼働状況（`status`） |
| `src/mail/` | メール取得・分類・下書き・送信・Slack カード化（`fetch`/`classify`/`draft`/`send`/`pipeline`/`slack_cards`） |
| `src/kpi/` | KPI 収集と承認フロー（`collector`/`approval`/`auto_approve`/`slack_approvals`） |
| `src/news/` | ニュース取得・要約（`fetch`/`summarize`/`pipeline`） |

- 設定: `config.yaml`（Slack チャンネル ID、ブリーフィング cron、メール分類カテゴリ等）
- 依存: `anthropic`、`slack_sdk`、`httpx`、`pyyaml`、`python-dotenv`

## influencer-agent（Eddie）

ニッチ条件でインフルエンサーを発見し、パーソナライズしたアウトリーチを送り、返信を分類してフォローするまでを自動化する。

```
  discovery/ (search → extract → filter)   ← ニッチ/ハッシュタグ/フォロワー条件
       │
       ▼
  outreach/ (campaign → personalize → send)
       │
       ▼
  followup/ (webhook_server → classify → notify)
       │
       ▼
  kpi/ (report)
```

| モジュール | 内容 |
|---|---|
| `src/discovery/` | 探索・抽出・フィルタ（フォロワー数/エンゲージ率/メール有無等の条件） |
| `src/outreach/` | キャンペーン・パーソナライズ・送信 |
| `src/followup/` | 受信 Webhook サーバ・返信分類・通知 |
| `src/kpi/` | アウトリーチ KPI レポート |
| `src/shared/` | 設定・DB・データモデル共通層 |

- 設定: `config.yaml`（ニッチキーワード、ハッシュタグ、フィルタ条件）

## ディレクトリ構成

```
automation-cloud/
├── ai-hub/
│   ├── src/{hub,mail,kpi,news}/   # ドメイン別モジュール
│   ├── config.yaml  cron_setup.json  setup.sh
│   ├── skills/  tasks/  tests/  docs/
│   └── requirements.txt
├── influencer-agent/
│   ├── src/{discovery,outreach,followup,kpi,shared}/
│   ├── config.yaml  setup.sh
│   ├── skills/  tasks/  tests/  docs/
│   └── requirements.txt
├── scripts/
├── requirements-cloud.txt
└── .github/workflows/
```

## セットアップ

各エージェントは独立してセットアップする。

```bash
# 例: ai-hub
cd ai-hub
cp .env.example .env          # 認証情報を設定（.env は gitignore 済み）
pip install -r requirements.txt
bash setup.sh

# influencer-agent も同様
cd ../influencer-agent
cp .env.example .env
pip install -r requirements.txt
bash setup.sh
```

`config.yaml`（Slack チャンネル ID、cron、フィルタ条件等）を編集してから cron に登録する。

## ステータス

個人プロジェクト。各エージェントの実装は本リポジトリの通り。認証情報・`config.yaml` を与えれば cron で自走する構成。運用実績値はここには記載しない。

## License

MIT
