from enum import Enum


class Reason(str, Enum):
    DM = "dm"
    MENTION = "mention"


# Subtypes that carry a real, human-authored message. Everything else
# (bot_message, message_changed, message_deleted, channel_join, ...) is dropped.
ALLOWED_SUBTYPES = {None, "thread_broadcast", "file_share"}


def classify(event: dict, my_user_id: str) -> Reason | None:
    """Return why this event should be forwarded, or None to ignore it."""
    if event.get("type") != "message":
        return None
    if event.get("subtype") not in ALLOWED_SUBTYPES:
        return None
    # Bot/app authored: also prevents forwarding loops.
    if event.get("bot_id") or "bot_profile" in event:
        return None

    sender = event.get("user")
    if not sender or sender == my_user_id:
        return None

    if f"<@{my_user_id}" in (event.get("text") or ""):  # also matches <@U123|name>
        return Reason.MENTION
    if event.get("channel_type") == "im":
        return Reason.DM
    return None
