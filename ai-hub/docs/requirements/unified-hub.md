# 要件定義: 統合AIハブ

## 概要

BBの「AIがホワイトカラー業務を奪う5段階」フレームワークに基づき、
既存の全プロジェクト（CFO Agent, Eddie, Trading bots, Lead Gen）を
Slack統合入口 + メール自動化 + クロスKPI承認フローで結合するシステム。

**目標: 第4段階（人間承認つき自動運転）を全業務で実現し、第5段階を目指す。**

---

## プロジェクト構成（3モジュール）

```
┌──────────────────────────────────────────────────────┐
│                    ai-hub                             │
│                                                       │
│  Module 1: Slack統合入口ハブ (hub)                    │
│  Module 2: メール自動化 (mail)                        │
│  Module 3: クロスKPI + 承認フロー (kpi)               │
│                                                       │
│  既存システムへの橋渡し:                              │
│  ├─ CFO Agent → Vercel API経由                        │
│  ├─ Eddie → SQLite直接読み取り                        │
│  ├─ Trading → Discord webhook / log読み取り            │
│  └─ OpenClaw → Gateway API / Skill連携                │
└──────────────────────────────────────────────────────┘
```

---

## Module 1: Slack統合入口ハブ

### ユーザーストーリー

AS A アプリ運営者
I WANT TO 全プロジェクトの情報をSlack1箇所で把握したい
SO THAT 分散したツール間を行き来する時間をゼロにできる

### 受入条件

#### 機能要件
- [ ] H-1: OpenClaw HEARTBEATに全プロジェクト横断チェックを設定
- [ ] H-2: 毎朝9:00 JSTに #daily-briefing チャンネルへ統合レポート投稿
- [ ] H-3: Eddie KPI（リード数/返信率/パイプライン）をSlackに転送
- [ ] H-4: Trading P&L（ポジション/損益）をSlackに転送
- [ ] H-5: CFO要約（売上/経費/キャッシュ残高）をSlackに含める
- [ ] H-6: Slack Slash Command `/hub-status` で全プロジェクト状態をオンデマンド取得
- [ ] H-7: Slackチャンネル自動作成（#daily-briefing, #mail-inbox, #approvals）

#### 非機能要件
- 既存のOpenClaw Slack接続を再利用（新規App不要）
- 既存のCFO Agent Slackは独立維持（干渉しない）

---

## Module 2: メール自動化

### ユーザーストーリー

AS A アプリ運営者
I WANT TO メールをAIが自動分類し返信案を作ってほしい
SO THAT メール対応時間を80%削減し、承認データを蓄積できる

### 受入条件

#### 機能要件
- [ ] M-1: Gmail IMAPで1時間ごとにメール取得（Cronジョブ）
- [ ] M-2: Claude APIで分類（urgent/needs_reply/info_only/spam）
- [ ] M-3: needs_reply メールにはClaude APIで返信ドラフトを生成
- [ ] M-4: Slack #mail-inbox に分類結果+返信案をBlock Kit形式で投稿
- [ ] M-5: Slackボタンで「承認送信」「編集して送信」「無視」を選択
- [ ] M-6: 「承認送信」で実際にGmail SMTP経由で返信を送信
- [ ] M-7: 承認/却下の履歴をDBに蓄積（将来の自動承認学習用）
- [ ] M-8: urgentメールは即座にTelegramにも通知
- [ ] M-9: 既読/処理済みメールの重複処理を防止

#### 非機能要件
- Gmail App Password（OAuth不要、IMAP用）
- 1時間あたり最大100通処理
- 承認履歴からパターン学習（v2で自動承認へ）

---

## Module 3: クロスKPI + 承認フロー

### ユーザーストーリー

AS A アプリ運営者
I WANT TO 全プロジェクトのKPIを1画面で見て、承認が必要なアクションを一元管理したい
SO THAT 意思決定のスピードを上げ、将来的にAI自動承認に移行できる

### 受入条件

#### 機能要件
- [ ] K-1: 全プロジェクトのKPIを統合DBに集約（30分ごと）
- [ ] K-2: Slack #daily-briefing に全KPIを1メッセージで投稿（毎朝9:00）
- [ ] K-3: 承認キューの管理（各プロジェクトの承認待ちアクション）
- [ ] K-4: Slack #approvals チャンネルに承認待ちアイテムを投稿
- [ ] K-5: Slackボタンで承認/却下（1クリック）
- [ ] K-6: 承認履歴をDB保存（who/when/what/decision）
- [ ] K-7: 承認パターン分析レポート（週次: 自動承認率の推定）
- [ ] K-8: 自動承認ルール設定（条件マッチで人間スキップ）

#### データソース
| プロジェクト | KPI | 取得方法 |
|------------|-----|---------|
| Eddie | リード数/返信率/契約数/コスト | SQLite直接 |
| CFO Agent | 売上/経費/利益/キャッシュ残高 | Vercel API or freee API |
| Trading | P&L/ポジション/勝率 | ログファイル or Discord |
| Lead Gen | リード数/品質スコア | DB直接 |
| Note.com | PV/フォロワー/記事数 | note API (既存MCP) |

#### 承認対象アクション
| アクション | ソース | 承認レベル |
|-----------|--------|-----------|
| メール返信送信 | Module 2 | 低（将来自動化） |
| インフルエンサー契約 | Eddie | 高（人間必須） |
| 仕訳登録 | CFO Agent | 中（金額による） |
| 広告予算変更 | 将来 | 高（人間必須） |

#### 非機能要件
- 承認は5秒以内にSlackに反映
- 承認ログは改ざん不可（append-only）
- 自動承認ルールは明示的なON/OFF

---

## 制約事項

### 技術スタック
- **言語**: Python 3.11+（既存Eddie/Tradingと統一）
- **エージェント基盤**: OpenClaw（既存Gateway活用）
- **通知**: Slack（メイン）+ Telegram（緊急時）
- **DB**: SQLite（ローカル統合DB）
- **メール**: Gmail IMAP/SMTP（imaplib + smtplib）
- **AI**: Claude API（分類・生成・承認判断）
- **Slack投稿**: slack_sdk（OpenClawのBot Token再利用）

### 既存システムとの連携
- CFO Agent: Vercel上のAPI直接呼び出し or freee API直接
- Eddie: ~/influencer-agent/data/influencer_agent.db 直接読み取り
- OpenClaw: ~/.openclaw/ のHEARTBEAT.md, cron/jobs.json 編集
- Trading: ログファイル解析 or Discord webhook

### 禁止事項
- 既存のCFO Agent Slackアプリを変更しない
- 既存のOpenClaw Gateway設定を壊さない
- 機密情報（APIキー等）をDBに平文保存しない

---

## ファイル構成

```
~/ai-hub/
├── config.yaml                     # 統合設定
├── .env                            # APIキー
├── data/
│   └── hub.db                      # 統合SQLite DB
├── src/
│   ├── hub/                        # Module 1: Slack統合
│   │   ├── briefing.py             # 統合日次レポート生成
│   │   ├── slack_post.py           # Slack投稿ユーティリティ
│   │   └── status.py               # /hub-status コマンド
│   ├── mail/                       # Module 2: メール自動化
│   │   ├── fetch.py                # Gmail IMAP取得
│   │   ├── classify.py             # Claude分類
│   │   ├── draft.py                # 返信ドラフト生成
│   │   ├── send.py                 # SMTP送信
│   │   └── slack_cards.py          # Slack Block Kit表示
│   ├── kpi/                        # Module 3: クロスKPI
│   │   ├── collector.py            # 各プロジェクトKPI収集
│   │   ├── dashboard.py            # 統合ダッシュボード
│   │   ├── approval.py             # 承認フローエンジン
│   │   ├── auto_approve.py         # 自動承認ルール
│   │   └── slack_approvals.py      # Slack承認UI
│   └── shared/
│       ├── config.py               # 設定読み込み
│       ├── db.py                   # SQLite
│       └── slack_client.py         # Slack SDK共通
├── skills/                         # OpenClaw Skills
│   ├── eddie-hub/SKILL.md          # 統合ハブスキル
│   ├── eddie-mail/SKILL.md         # メール自動化スキル
│   └── eddie-approvals/SKILL.md    # 承認フロースキル
├── tests/
├── requirements.txt
└── setup.sh
```

---

## 実装優先順位

| 順番 | モジュール | 期間 | 依存関係 |
|-----|-----------|------|---------|
| 1 | shared (DB, config, Slack client) | 1日 | なし |
| 2 | Module 1: Slack統合入口 | 3日 | shared |
| 3 | Module 2: メール自動化 | 4日 | shared + Module 1 |
| 4 | Module 3: クロスKPI + 承認 | 5日 | shared + Module 1 |
| 5 | OpenClaw Skill + HEARTBEAT設定 | 1日 | 全モジュール |

**合計: 約2週間**
