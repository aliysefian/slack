# Slack → Telegram notification bridge

FastAPI service that receives Slack Events API webhooks and forwards (a) DMs to you and (b) any message that mentions `<@YOUR_ID>` to a Telegram chat. Bot messages, edits/deletes, join events and your own messages are ignored.

```
app/main.py        webhook endpoint, URL verification, dedupe, background forwarding
app/security.py    HMAC-SHA256 signature verification
app/filters.py     DM / mention / bot filtering
app/slack.py       users.info + chat.getPermalink lookups (best-effort)
app/telegram.py    sendMessage with retry / 429 handling
app/formatting.py  HTML message layout
```

## 1. Telegram bot

1. In Telegram, open **@BotFather** → `/newbot` → pick a name and username → copy the token (`TELEGRAM_BOT_TOKEN`).
2. Open your new bot and press **Start** (send it any message). Bots can't message you first.
3. Get your chat ID:
   ```bash
   curl -s "https://api.telegram.org/bot<TOKEN>/getUpdates" | python3 -m json.tool
   ```
   Use `result[0].message.chat.id` as `TELEGRAM_CHAT_ID`. (Alternatively message **@userinfobot**.)

## 2. Slack app

1. <https://api.slack.com/apps> → **Create New App → From scratch**.
2. **Basic Information → App Credentials**: copy the **Signing Secret** (`SLACK_SIGNING_SECRET`).
3. **OAuth & Permissions → Scopes**. Add:
   - Bot token scopes: `im:history`, `im:read`, `channels:history`, `groups:history`, `users:read`
   - **User token scopes** (same list) — needed so Slack sends events for *your* conversations, see the note below.
4. **Install App** to the workspace. Copy the **Bot User OAuth Token** (`xoxb-…`) → `SLACK_BOT_TOKEN`.
5. Your member ID: Slack profile → ⋮ → **Copy member ID** → `MY_SLACK_USER_ID`.
6. Deploy the service (section 3) so it is reachable over public HTTPS, then **Event Subscriptions → Enable Events**, Request URL `https://your.domain/slack/events`. It should turn green ("Verified") — see section 4.
7. Subscribe to events:
   - **Subscribe to events on behalf of users:** `message.im`, `message.channels`, `message.groups`
   - (Optional) bot events with the same names, for channels where the bot is invited.
8. Reinstall the app when Slack prompts you.

> **Important:** a bot only receives events for conversations it is a member of. It will *not* see your DMs with other people or channels it hasn't joined. Subscribing under **"events on behalf of users"** is what delivers messages from your own DMs and joined channels. If you only subscribe to bot events, you'll only get DMs to the bot and channels you invite it to. `channels:read`/`groups:read` are not requested, so channels show as IDs rather than names; add them if you want to extend `slack.py`.

## 3. Deploy

```bash
cp .env.example .env     # fill in all five secrets
docker compose up -d --build
docker compose ps        # STATUS should become "healthy"
docker compose logs -f
```

The container listens on `127.0.0.1:8000`. Slack requires public HTTPS, so put a reverse proxy in front, e.g. Caddy:

```
your.domain {
    reverse_proxy 127.0.0.1:8000
}
```

or a Cloudflare Tunnel / ngrok (`ngrok http 8000`) for testing. Run a **single** worker (the retry-dedupe cache is in-memory).

Local tests: `pip install -r requirements.txt pytest && pytest`

## 4. How verification works

**Signature.** Every Slack request carries `X-Slack-Request-Timestamp` and `X-Slack-Signature`. `app/security.py` rebuilds `v0:{timestamp}:{raw_body}`, computes HMAC-SHA256 with the signing secret, and compares it to the header with `hmac.compare_digest`. Requests more than 5 minutes off are rejected (replay protection). The **raw** body bytes are used, not re-serialised JSON. Invalid → HTTP 401.

**URL verification.** When you save the Request URL, Slack POSTs `{"type":"url_verification","challenge":"…"}` (signed). After the signature check, the endpoint replies with the `challenge` value as plain text.

**Retries.** Slack expects a response within 3 seconds, otherwise it retries. The endpoint acks immediately and does name lookup + Telegram delivery in a background task; duplicate `event_id`s are dropped.

## Troubleshooting

- Request URL not verifying: check the proxy forwards the body unmodified and `SLACK_SIGNING_SECRET` is correct (logs show `rejected request with invalid signature`).
- Nothing arrives in Telegram: logs show `telegram rejected message` with Telegram's reason (usually you haven't pressed Start, or wrong chat ID).
- No events for your DMs: see the Important note in section 2.
