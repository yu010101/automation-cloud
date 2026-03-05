import type { Env } from "./types";

export async function sendTelegram(
  env: Env,
  message: string
): Promise<boolean> {
  const url = `https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`;

  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      chat_id: env.TELEGRAM_CHAT_ID,
      text: message,
      parse_mode: "Markdown",
    }),
  });

  return resp.ok;
}
