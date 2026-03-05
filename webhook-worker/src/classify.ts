import Anthropic from "@anthropic-ai/sdk";
import type { ReplyCategory } from "./types";

const CATEGORIES: ReplyCategory[] = [
  "interested",
  "meeting_request",
  "not_interested",
  "question",
  "out_of_office",
  "wrong_person",
];

const SYSTEM_PROMPT = `You are an email reply classifier for influencer outreach campaigns.
Classify the reply into exactly one of these categories: ${CATEGORIES.join(", ")}

Rules:
- "interested": They express interest, want to know more, or ask about compensation details
- "meeting_request": They explicitly ask to schedule a call or meeting
- "not_interested": They decline, say no, or express disinterest
- "question": They ask questions not directly about interest (e.g., "what's the app about?")
- "out_of_office": Auto-replies, vacation messages, or temporary unavailability
- "wrong_person": They say they're not the right person, wrong email, etc.

Output ONLY the category name, nothing else.`;

export async function classifyReply(
  replyText: string,
  apiKey: string
): Promise<ReplyCategory> {
  const client = new Anthropic({ apiKey });

  const response = await client.messages.create({
    model: "claude-haiku-4-5-20251001",
    max_tokens: 20,
    system: SYSTEM_PROMPT,
    messages: [
      { role: "user", content: `Classify this reply:\n\n${replyText}` },
    ],
  });

  const category = (
    response.content[0].type === "text" ? response.content[0].text : ""
  )
    .trim()
    .toLowerCase() as ReplyCategory;

  return CATEGORIES.includes(category) ? category : "question";
}
