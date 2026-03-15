import asyncio
import logging
from typing import Optional

import httpx
from app.domain.models import InstagramAccount
from app.domain.entities import Reel
from app.domain.repositories import InstagramPublisher


class InstagramGraphApiClient(InstagramPublisher):

    BASE_URL = "https://graph.instagram.com"

    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.logger = logging.getLogger(__name__)

    async def get_token(self, code):
        async with httpx.AsyncClient() as client:
            short_resp = await client.post(
                "https://api.instagram.com/oauth/access_token",
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "authorization_code",
                    "redirect_uri": self.redirect_uri,
                    "code": code
                }
            )
            short_data = short_resp.json()

            if "access_token" not in short_data:
                raise Exception(short_data)

            self.logger.info("Short token response: expires_in=%s", short_data.get("expires_in"))

            short_token = short_data["access_token"]
            expires_in = int(short_data.get("expires_in", 0))

            # Новый Instagram Platform (instagram_business_*) уже возвращает long-lived токен
            if expires_in > 86400:
                return short_token, expires_in

            return await self.update_token(short_token)

    async def update_token(self, current_token: str):
        async with httpx.AsyncClient() as client:
            long_resp = await client.get(
                f"{self.BASE_URL}/access_token",
                params={
                    "grant_type": "ig_exchange_token",
                    "client_secret": self.client_secret,
                    "access_token": current_token
                }
            )
            long_data = long_resp.json()
            if "access_token" not in long_data:
                raise Exception(long_data)

            return long_data["access_token"], long_data["expires_in"]
        
    async def refresh_long_lived_token(self, long_token: str):
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.BASE_URL}/refresh_access_token",
                params={
                    "grant_type": "ig_refresh_token",
                    "access_token": long_token,
                }
            )
            data = resp.json()
            if "access_token" not in data:
                raise Exception(data)
            return data["access_token"], data["expires_in"]

    async def get_reel_views(self, media_id: str, access_token: str) -> Optional[int]:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.BASE_URL}/{media_id}/insights",
                params={"metric": "views", "period": "lifetime", "access_token": access_token},
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
                    params={"fields": "permalink", "access_token": access_token},
                )
                return resp.json().get("permalink")
        except Exception:
            return None

    async def get_account_info(self, long_token: str):
        async with httpx.AsyncClient() as client:
            me_resp = await client.get(
                f"{self.BASE_URL}/me",
                params={
                    "fields": "id,username",
                    "access_token": long_token
                }
            )
            return me_resp.json()
          

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
            payload["trial_params"] = {
                "graduation_strategy": "MANUAL"
            }

        if reel.thumbnail_url:
            payload["thumb_offset"] = 0  # можно расширить
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, data=payload)
            response.raise_for_status()

            return response.json()["id"]

    async def _wait_for_container(self, creation_id: str, account: InstagramAccount):
        url = f"{self.BASE_URL}/{creation_id}"

        params = {
            "fields": "status_code,status",
            "access_token": account.access_token
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
                    sleep_seconds, creation_id, status_code
                )
                await asyncio.sleep(sleep_seconds)
                sleep_seconds += sleep_seconds


    async def _publish_media(self, creation_id: str, account: InstagramAccount) -> str:
        url = f"{self.BASE_URL}/{account.instagram_id}/media_publish"

        payload = {
            "creation_id": creation_id,
            "access_token": account.access_token
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, data=payload)
            response.raise_for_status()

            return response.json()["id"]