import { createClient, type Client } from "@libsql/client/web";
import type { Env } from "./types";

export function getDb(env: Env): Client {
  return createClient({
    url: env.TURSO_EDDIE_URL,
    authToken: env.TURSO_EDDIE_TOKEN,
  });
}

export async function updateOutreachStatus(
  db: Client,
  leadEmail: string,
  status: string,
  replyText?: string,
  replyCategory?: string
): Promise<void> {
  await db.execute({
    sql: `UPDATE outreach_logs SET status = ?, reply_text = ?, reply_category = ?, reply_at = CURRENT_TIMESTAMP
          WHERE influencer_id IN (SELECT id FROM influencers WHERE email = ?)
          AND status NOT IN ('replied', 'bounced', 'unsubscribed')`,
    args: [status, replyText ?? null, replyCategory ?? null, leadEmail],
  });
}

export async function getInfluencerByEmail(
  db: Client,
  email: string
): Promise<{ instagram_username: string; followers_count: number } | null> {
  const result = await db.execute({
    sql: "SELECT instagram_username, followers_count FROM influencers WHERE email = ?",
    args: [email],
  });
  if (result.rows.length === 0) return null;
  const row = result.rows[0];
  return {
    instagram_username: row.instagram_username as string,
    followers_count: row.followers_count as number,
  };
}

export async function updateInfluencerStatus(
  db: Client,
  username: string,
  status: string
): Promise<void> {
  await db.execute({
    sql: "UPDATE influencers SET status = ? WHERE instagram_username = ?",
    args: [status, username],
  });
}
