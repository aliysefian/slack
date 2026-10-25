import html
from datetime import datetime, timezone

from .filters import Reason


def slack_unescape(text: str) -> str:
    """Slack escapes only &, < and > in message text."""
    return text.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")


def format_message(
    *,
    reason: Reason,
    sender_name: str,
    sender_id: str,
    channel_id: str,
    text: str,
    ts: str,
    permalink: str | None,
) -> str:
    e = html.escape
    if reason is Reason.DM:
        header = f"💬 <b>DM</b> from <b>{e(sender_name)}</b> (<code>{e(sender_id)}</code>)"
    else:
        header = (
            f"🔔 <b>Mention</b> by <b>{e(sender_name)}</b> (<code>{e(sender_id)}</code>)"
            f" in <code>{e(channel_id)}</code>"
        )
    try:
        when = datetime.fromtimestamp(float(ts), timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    except ValueError:
        when = ts

    # Leave headroom under Telegram's 4096 limit so truncation never cuts the footer/tags.
    body = slack_unescape(text or "(no text)")
    if len(body) > 3500:
        body = body[:3500] + "…"
    lines = [header, f"<blockquote>{e(body)}</blockquote>", f"🕒 {when}"]
    if permalink:
        lines.append(f'<a href="{e(permalink, quote=True)}">Open in Slack</a>')
    return "\n".join(lines)
