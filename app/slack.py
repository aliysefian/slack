import logging

import httpx

log = logging.getLogger(__name__)
API = "https://slack.com/api"


class SlackClient:
    """Best-effort Slack lookups. Failures degrade to raw IDs, never block forwarding."""

    def __init__(self, token: str, http: httpx.AsyncClient):
        self._headers = {"Authorization": f"Bearer {token}"}
        self._http = http
        self._names: dict[str, str] = {}

    async def _call(self, method: str, params: dict) -> dict | None:
        try:
            r = await self._http.get(f"{API}/{method}", params=params, headers=self._headers)
            r.raise_for_status()
            data = r.json()
        except (httpx.HTTPError, ValueError):
            log.warning("slack api call failed", extra={"ctx": {"method": method}}, exc_info=True)
            return None
        if not data.get("ok"):
            log.warning("slack api error", extra={"ctx": {"method": method, "error": data.get("error")}})
            return None
        return data

    async def user_name(self, user_id: str) -> str:
        if user_id in self._names:
            return self._names[user_id]
        data = await self._call("users.info", {"user": user_id})
        if not data:
            return user_id
        user = data["user"]
        profile = user.get("profile", {})
        name = profile.get("display_name") or user.get("real_name") or user.get("name") or user_id
        self._names[user_id] = name
        return name

    async def permalink(self, channel: str, ts: str) -> str | None:
        data = await self._call("chat.getPermalink", {"channel": channel, "message_ts": ts})
        return data.get("permalink") if data else None
