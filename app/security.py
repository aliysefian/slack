import hashlib
import hmac
import time


def verify_slack_signature(
    *,
    signing_secret: str,
    timestamp: str | None,
    signature: str | None,
    body: bytes,
    tolerance: int = 300,
    now: float | None = None,
) -> bool:
    """Validate X-Slack-Signature: v0=HMAC_SHA256(secret, "v0:{ts}:{raw body}")."""
    if not timestamp or not signature:
        return False
    try:
        ts = int(timestamp)
    except ValueError:
        return False
    if abs((now if now is not None else time.time()) - ts) > tolerance:
        return False  # stale or future-dated: possible replay

    base = b"v0:" + timestamp.encode() + b":" + body
    expected = "v0=" + hmac.new(signing_secret.encode(), base, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
