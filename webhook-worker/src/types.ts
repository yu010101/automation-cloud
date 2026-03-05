export interface Env {
  ANTHROPIC_API_KEY: string;
  TURSO_EDDIE_URL: string;
  TURSO_EDDIE_TOKEN: string;
  TELEGRAM_BOT_TOKEN: string;
  TELEGRAM_CHAT_ID: string;
  WEBHOOK_SECRET?: string;
}

export interface SmartleadWebhook {
  event_type: string;
  sl_lead_email?: string;
  to_email?: string;
  preview_text?: string;
  [key: string]: unknown;
}

export type ReplyCategory =
  | "interested"
  | "meeting_request"
  | "not_interested"
  | "question"
  | "out_of_office"
  | "wrong_person";
