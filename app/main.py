import json
import logging
import time
from contextlib import asynccontextmanager

import httpx
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, Response

from .config import get_settings
from .filters import classify
from .formatting import format_message
from .logging_setup import setup_logging
from .security import verify_slack_signature
from .slack import SlackClient
from .telegram import TelegramClient

settings = get_settings()
setup_logging(settings.log_level)
log = logging.getLogger("bridge")

DEDUPE_TTL = 3600
_seen: dict[str, float] = {}  # event_id -> first-seen time (single-process; run 1 worker)


def _is_duplicate(event_id: str | None) -> bool:
    now = time.time()
    for k in [k for k, t in _seen.items() if now - t > DEDUPE_TTL]:
        del _seen[k]
    if not event_id:
        return False
    if event_id in _seen:
        return True
    _seen[event_id] = now
    return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as http:
        app.state.slack = SlackClient(settings.slack_bot_token, http)
        app.state.telegram = TelegramClient(settings.telegram_bot_token, settings.telegram_chat_id, http)
        log.info("bridge started")
        yield


app = FastAPI(title="slack-telegram-bridge", lifespan=lifespan)


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


async def forward(app: FastAPI, event: dict, reason) -> None:
    slack: SlackClient = app.state.slack
    telegram: TelegramClient = app.state.telegram
    try:
        sender, channel, ts = event["user"], event.get("channel", ""), event.get("ts", "")
        name = await slack.user_name(sender)
        link = await slack.permalink(channel, ts) if channel and ts else None
        msg = format_message(
            reason=reason,
            sender_name=name,
            sender_id=sender,
            channel_id=channel,
            text=event.get("text", ""),
            ts=ts,
            permalink=link,
        )
        ok = await telegram.send(msg)
        log.info("forwarded" if ok else "forward failed",
                 extra={"ctx": {"reason": reason.value, "channel": channel, "ts": ts}})
    except Exception:
        log.exception("unhandled error while forwarding")


@app.post("/slack/events")
async def slack_events(request: Request, background: BackgroundTasks):
    body = await request.body()  # raw bytes: the signature covers the exact payload
    if not verify_slack_signature(
        signing_secret=settings.slack_signing_secret,
        timestamp=request.headers.get("X-Slack-Request-Timestamp"),
        signature=request.headers.get("X-Slack-Signature"),
        body=body,
        tolerance=settings.slack_timestamp_tolerance,
    ):
        log.warning("rejected request with invalid signature")
        raise HTTPException(status_code=401, detail="invalid signature")

    try:
        payload = json.loads(body)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid json")

    kind = payload.get("type")
    if kind == "url_verification":
        return Response(content=payload.get("challenge", ""), media_type="text/plain")

    if kind == "event_callback":
        event = payload.get("event", {})
        reason = classify(event, settings.my_slack_user_id)
        if reason and not _is_duplicate(payload.get("event_id")):
            # Slack requires an ack within 3s; do the lookups + Telegram call afterwards.
            background.add_task(forward, request.app, event, reason)
        elif reason:
            log.info("duplicate event skipped", extra={"ctx": {"event_id": payload.get("event_id")}})

    return Response(status_code=200)
