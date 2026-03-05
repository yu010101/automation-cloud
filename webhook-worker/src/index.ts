import type { Env, SmartleadWebhook } from "./types";
import { classifyReply } from "./classify";
import {
  getDb,
  updateOutreachStatus,
  getInfluencerByEmail,
  updateInfluencerStatus,
} from "./db";
import { sendTelegram } from "./telegram";

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    // Health check
    if (url.pathname === "/health") {
      return Response.json({ status: "ok" });
    }

    // Only accept POST to /webhook/smartlead
    if (url.pathname !== "/webhook/smartlead" || request.method !== "POST") {
      return Response.json({ error: "not found" }, { status: 404 });
    }

    // Optional webhook secret validation
    if (env.WEBHOOK_SECRET) {
      const authHeader = request.headers.get("x-webhook-secret");
      if (authHeader !== env.WEBHOOK_SECRET) {
        return Response.json({ error: "unauthorized" }, { status: 401 });
      }
    }

    let payload: SmartleadWebhook;
    try {
      payload = (await request.json()) as SmartleadWebhook;
    } catch {
      return Response.json({ error: "invalid json" }, { status: 400 });
    }

    const eventType = payload.event_type || "";
    const leadEmail = payload.sl_lead_email || payload.to_email || "";

    console.log(`Webhook: ${eventType} for ${leadEmail}`);

    const db = getDb(env);

    if (eventType === "EMAIL_REPLY") {
      const replyText = (payload.preview_text as string) || "";

      // Classify with Claude
      const category = await classifyReply(replyText, env.ANTHROPIC_API_KEY);

      // Update DB
      await updateOutreachStatus(db, leadEmail, "replied", replyText, category);

      // Find influencer and update status
      const influencer = await getInfluencerByEmail(db, leadEmail);
      if (influencer) {
        if (category === "interested" || category === "meeting_request") {
          await updateInfluencerStatus(
            db,
            influencer.instagram_username,
            "negotiating"
          );
          await sendTelegram(
            env,
            `*New ${category} reply*\n` +
              `@${influencer.instagram_username}\n` +
              `Email: ${leadEmail}\n\n` +
              `_${replyText.slice(0, 200)}_`
          );
        } else if (category === "not_interested") {
          await updateInfluencerStatus(
            db,
            influencer.instagram_username,
            "rejected"
          );
        }
      }

      return Response.json({ status: "ok", category });
    }

    if (eventType === "EMAIL_BOUNCE") {
      await updateOutreachStatus(db, leadEmail, "bounced");
      return Response.json({ status: "ok", action: "bounced" });
    }

    if (eventType === "LEAD_UNSUBSCRIBED") {
      await updateOutreachStatus(db, leadEmail, "unsubscribed");
      return Response.json({ status: "ok", action: "unsubscribed" });
    }

    return Response.json({ status: "ok", action: "ignored" });
  },
};
