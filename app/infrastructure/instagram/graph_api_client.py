import asyncio
import logging
from typing import Optional

import httpx
from app.domain.models import InstagramAccount
from app.domain.entities import Reel
from app.domain.repositories import InstagramPublisher


class InstagramGraphApiClient(InstagramPublisher):

    BASE_URL = "https://graph.facebook.com/v21.0"
    IG_BASE_URL = "https://graph.instagram.com"

    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.logger = logging.getLogger(__name__)

    # ──────────────────────────────────────────────
    #  OAuth: получение и обмен токенов
    # ──────────────────────────────────────────────

    async def get_token(self, code: str):
        """
        Шаг 1: Обмен authorization code на short-lived Facebook User Token.
        Шаг 2: Обмен short-lived токена на long-lived (60 дней).

        Используется Facebook OAuth endpoint, т.к. Instagram Basic Display API
        deprecated с декабря 2024.
        """
        async with httpx.AsyncClient() as client:
            # Шаг 1: code → short-lived token (через Facebook OAuth)
            short_resp = await client.get(
                f"{self.BASE_URL}/oauth/access_token",
                params={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uri": self.redirect_uri,
                    "code": code,
                },
            )
            short_data = short_resp.json()

            if "access_token" not in short_data:
                raise Exception(f"Ошибка получения short-lived токена: {short_data}")

            short_token = short_data["access_token"]

            # Шаг 2: short-lived → long-lived
            return await self.exchange_for_long_lived_token(short_token)

    async def exchange_for_long_lived_token(self, short_token: str):
        """
        Обмен short-lived Facebook User Token (1 час) на long-lived (60 дней).
        Endpoint: GET /oauth/access_token с grant_type=fb_exchange_token
        """
        async with httpx.AsyncClient() as client:
            long_resp = await client.get(
                f"{self.BASE_URL}/oauth/access_token",
                params={
                    "grant_type": "fb_exchange_token",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "fb_exchange_token": short_token,
                },
            )
            long_data = long_resp.json()

            if "access_token" not in long_data:
                raise Exception(f"Ошибка обмена на long-lived токен: {long_data}")

            return long_data["access_token"], long_data.get("expires_in", 5184000)

    # Обратная совместимость: старое имя метода
    update_token = exchange_for_long_lived_token

    async def refresh_long_lived_token(self, long_token: str):
        """
        Обновление long-lived токена (продление ещё на 60 дней).
        Можно вызывать, пока токен ещё валиден.
        """
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.BASE_URL}/oauth/access_token",
                params={
                    "grant_type": "fb_exchange_token",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "fb_exchange_token": long_token,
                },
            )
            data = resp.json()

            if "access_token" not in data:
                raise Exception(f"Ошибка обновления токена: {data}")

            return data["access_token"], data.get("expires_in", 5184000)

    # ──────────────────────────────────────────────
    #  Информация об аккаунте
    # ──────────────────────────────────────────────

    async def get_account_info(self, long_token: str):
        """
        Получение Instagram Business Account ID через Facebook Pages.
        Цепочка: User Token → Pages → Instagram Business Account.
        """
        async with httpx.AsyncClient() as client:
            # Получаем список страниц пользователя
            pages_resp = await client.get(
                f"{self.BASE_URL}/me/accounts",
                params={
                    "fields": "id,name,access_token,instagram_business_account",
                    "access_token": long_token,
                },
            )
            pages_data = pages_resp.json()

            if "data" not in pages_data:
                raise Exception(f"Ошибка получения страниц: {pages_data}")

            # Ищем страницу с привязанным Instagram Business аккаунтом
            for page in pages_data["data"]:
                ig_account = page.get("instagram_business_account")
                if ig_account:
                    ig_id = ig_account["id"]

                    # Получаем username Instagram аккаунта
                    ig_resp = await client.get(
                        f"{self.BASE_URL}/{ig_id}",
                        params={
                            "fields": "id,username,profile_picture_url,name",
                            "access_token": long_token,
                        },
                    )
                    ig_data = ig_resp.json()
                    ig_data["page_access_token"] = page.get("access_token")
                    ig_data["page_id"] = page["id"]
                    ig_data["page_name"] = page.get("name")
                    return ig_data

            raise Exception(
                "Не найден Instagram Business аккаунт. "
                "Убедитесь, что к Facebook-странице привязан Instagram Professional аккаунт."
            )

    # ──────────────────────────────────────────────
    #  Аналитика: просмотры и ссылки
    # ──────────────────────────────────────────────

    async def get_reel_views(self, media_id: str, access_token: str) -> Optional[int]:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.BASE_URL}/{media_id}/insights",
                params={
                    "metric": "views",
                    "period": "lifetime",
                    "access_token": access_token,
                },
            )
            data = resp.json()

            if "error" in data:
                msg = data["error"].get("message", "")
                if "does not support" in msg:
                    return None
                raise Exception(data["error"])

            for item in data.get("data", []):
                if item.get("name") == "views":
                    if "value" in item:
                        return item["value"]
                    values = item.get("values", [])
                    if values:
                        return values[0].get("value")
        return None

    async def get_reel_permalink(self, media_id: str, access_token: str) -> Optional[str]:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self.BASE_URL}/{media_id}",
                    params={
                        "fields": "permalink",
                        "access_token": access_token,
                    },
                )
                return resp.json().get("permalink")
        except Exception:
            return None

    # ──────────────────────────────────────────────
    #  Публикация Reels
    # ──────────────────────────────────────────────

    async def publish_reel(self, reel: Reel, account: InstagramAccount) -> str:
        creation_id = await self._create_media_container(reel, account)
        await self._wait_for_container(creation_id, account)
        return await self._publish_media(creation_id, account)

    async def _create_media_container(self, reel: Reel, account: InstagramAccount) -> str:
        url = f"{self.BASE_URL}/{account.instagram_id}/media"

        payload = {
            "media_type": "REELS",
            "video_url": reel.video_url,
            "caption": reel.caption,
            "access_token": account.access_token,
        }
        if reel.is_trial:
            payload["trial_params"] = '{"graduation_strategy": "MANUAL"}'

        if reel.thumbnail_url:
            payload["thumb_offset"] = 0

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, data=payload)
            response.raise_for_status()
            return response.json()["id"]

    async def _wait_for_container(self, creation_id: str, account: InstagramAccount):
        url = f"{self.BASE_URL}/{creation_id}"
        params = {
            "fields": "status_code,status",
            "access_token": account.access_token,
        }
        sleep_seconds = 10

        async with httpx.AsyncClient() as client:
            while True:
                response = await client.get(url, params=params)
                response.raise_for_status()

                data = response.json()
                status_code = data.get("status_code")

                if status_code == "FINISHED":
                    return
                if status_code in ("ERROR", "EXPIRED"):
                    raise Exception(
                        f"Media container {creation_id} failed with status {status_code!r}: "
                        f"{data.get('status', '')}"
                    )

                self.logger.info(
                    "Waiting %s seconds for container %s (status: %s)",
                    sleep_seconds,
                    creation_id,
                    status_code,
                )
                await asyncio.sleep(sleep_seconds)
                sleep_seconds = min(sleep_seconds * 2, 120)  # cap at 2 min

    async def _publish_media(self, creation_id: str, account: InstagramAccount) -> str:
        url = f"{self.BASE_URL}/{account.instagram_id}/media_publish"

        payload = {
            "creation_id": creation_id,
            "access_token": account.access_token,
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, data=payload)
            response.raise_for_status()
            return response.json()["id"]
