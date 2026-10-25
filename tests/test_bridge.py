import hashlib
import hmac
import json
import os
import time

os.environ.update(
    SLACK_BOT_TOKEN="xoxb-test",
    SLACK_SIGNING_SECRET="secret",
    MY_SLACK_USER_ID="UME",
    TELEGRAM_BOT_TOKEN="t",
    TELEGRAM_CHAT_ID="1",
)

from fastapi.testclient import TestClient  # noqa: E402

from app.filters import Reason, classify  # noqa: E402
from app.main import app  # noqa: E402
from app.security import verify_slack_signature  # noqa: E402


def sign(body: bytes, ts: str, secret="secret") -> str:
    return "v0=" + hmac.new(secret.encode(), b"v0:" + ts.encode() + b":" + body, hashlib.sha256).hexdigest()


def post(client, payload, secret="secret", ts=None):
    body = json.dumps(payload).encode()
    ts = ts or str(int(time.time()))
    return client.post(
        "/slack/events",
        content=body,
        headers={"X-Slack-Request-Timestamp": ts, "X-Slack-Signature": sign(body, ts, secret)},
    )


def test_signature():
    ts = str(int(time.time()))
    assert verify_slack_signature(signing_secret="secret", timestamp=ts, signature=sign(b"x", ts), body=b"x")
    assert not verify_slack_signature(signing_secret="secret", timestamp=ts, signature=sign(b"y", ts), body=b"x")
    old = str(int(time.time()) - 1000)
    assert not verify_slack_signature(signing_secret="secret", timestamp=old, signature=sign(b"x", old), body=b"x")


def test_classify():
    dm = {"type": "message", "channel_type": "im", "user": "U1", "text": "hi"}
    assert classify(dm, "UME") is Reason.DM
    assert classify({**dm, "user": "UME"}, "UME") is None
    assert classify({**dm, "bot_id": "B1"}, "UME") is None
    assert classify({**dm, "subtype": "message_changed"}, "UME") is None
    ch = {"type": "message", "channel_type": "channel", "user": "U1", "text": "yo <@UME>"}
    assert classify(ch, "UME") is Reason.MENTION
    assert classify({**ch, "text": "yo <@UOTHER>"}, "UME") is None


def test_endpoint():
    with TestClient(app) as c:
        r = post(c, {"type": "url_verification", "challenge": "abc"})
        assert r.status_code == 200 and r.text == "abc"
        assert post(c, {"type": "url_verification", "challenge": "abc"}, secret="bad").status_code == 401
        assert c.get("/healthz").json() == {"status": "ok"}
