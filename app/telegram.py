import asyncio
import logging

import httpx

log = logging.getLogger(__name__)
MAX_LEN = 4096


class TelegramClient:
    def __init__(self, token: str, chat_id: str, http: httpx.AsyncClient):
        self._url = f"https://api.telegram.org/bot{token}/sendMessage"
        self._chat_id = chat_id
        self._http = http

    async def send(self, html: str, retries: int = 3) -> bool:
        payload = {
            "chat_id": self._chat_id,
            "text": html[:MAX_LEN],
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        for attempt in range(1, retries + 1):
            try:
                r = await self._http.post(self._url, json=payload)
            except httpx.HTTPError:
                log.warning("telegram request error", extra={"ctx": {"attempt": attempt}}, exc_info=True)
                await asyncio.sleep(2**attempt)
                continue
            if r.status_code == 200:
                return True
            if r.status_code == 429:
                wait = r.json().get("parameters", {}).get("retry_after", 2**attempt)
                await asyncio.sleep(min(wait, 30))
                continue
            if r.status_code >= 500:
                await asyncio.sleep(2**attempt)
                continue
            # 4xx (bad token, wrong chat id, bad HTML): retrying won't help.
            log.error("telegram rejected message", extra={"ctx": {"status": r.status_code, "body": r.text[:300]}})
            return False
        log.error("telegram send gave up", extra={"ctx": {"retries": retries}})
        return False
