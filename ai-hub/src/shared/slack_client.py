"""Shared Slack client using OpenClaw's existing bot token."""

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from .config import env, env_opt

_client: WebClient | None = None


def get_slack() -> WebClient:
    global _client
    if _client is None:
        _client = WebClient(token=env("SLACK_BOT_TOKEN"))
    return _client


def post_message(channel: str, text: str = "", blocks: list | None = None) -> str:
    """Post a message to Slack. Returns the message timestamp."""
    resp = get_slack().chat_postMessage(
        channel=channel,
        text=text,
        blocks=blocks,
        unfurl_links=False,
    )
    return resp["ts"]


def update_message(channel: str, ts: str, text: str = "", blocks: list | None = None):
    """Update an existing Slack message."""
    get_slack().chat_update(channel=channel, ts=ts, text=text, blocks=blocks)


def post_ephemeral(channel: str, user: str, text: str):
    """Post an ephemeral message visible only to one user."""
    get_slack().chat_postEphemeral(channel=channel, user=user, text=text)


def ensure_channel(name: str) -> str:
    """Find or create a Slack channel. Returns channel ID."""
    client = get_slack()
    # Search existing channels
    try:
        resp = client.conversations_list(types="public_channel,private_channel", limit=1000)
        for ch in resp["channels"]:
            if ch["name"] == name:
                return ch["id"]
    except SlackApiError:
        pass
    # Create if not found
    try:
        resp = client.conversations_create(name=name)
        return resp["channel"]["id"]
    except SlackApiError as e:
        if "name_taken" in str(e):
            # Channel exists but bot isn't in it; try to join
            resp = client.conversations_list(types="public_channel", limit=1000)
            for ch in resp["channels"]:
                if ch["name"] == name:
                    client.conversations_join(channel=ch["id"])
                    return ch["id"]
        raise


def add_reaction(channel: str, ts: str, emoji: str):
    """Add a reaction to a message."""
    try:
        get_slack().reactions_add(channel=channel, timestamp=ts, name=emoji)
    except SlackApiError:
        pass  # Already reacted or permission issue
