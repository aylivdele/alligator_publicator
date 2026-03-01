import asyncio
import logging
from typing import Tuple

import httpx
import requests
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

            short_token = short_data["access_token"]

            # Шаг 2: обмен на долгоживущий токен (60 дней)
            long_resp = await client.get(
                f"{self.BASE_URL}/access_token",
                params={
                    "grant_type": "ig_exchange_token",
                    "client_secret": self.client_secret,
                    "access_token": short_token
                }
            )
            long_data = long_resp.json()
            return long_data["access_token"], long_data["expires_in"]
        
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
        creation_id = self._create_media_container(reel, account)
        await self._wait_for_container(creation_id, account)
        return self._publish_media(creation_id, account)

    def _create_media_container(self, reel: Reel, account: InstagramAccount) -> str:
        url = f"{self.BASE_URL}/{account.instagram_id}/media"

        payload = {
            "media_type": "REELS",
            "video_url": reel.video_url,
            "caption": reel.caption,
            "access_token": account.access_token
        }

        if reel.thumbnail_url:
            payload["thumb_offset"] = 0  # можно расширить

        response = requests.post(url, data=payload)
        response.raise_for_status()

        return response.json()["id"]
    
    async def _wait_for_container(self, creation_id: str, account: InstagramAccount):
        url = f"{self.BASE_URL}/{creation_id}"

        params={
            "fields": "status_code,status",
            "access_token": account.access_token
        }
        sleep_seconds = 10

        finished = False
        while not finished:
            response = requests.get(url, params=params)
            response.raise_for_status()

            finished = response.json()["status_code"] == "FINISHED"
            if not finished:
                self.logger.info(f"Waiting {sleep_seconds} seconds for container {creation_id} to upload")
                await asyncio.sleep(sleep_seconds)
                sleep_seconds += sleep_seconds


    def _publish_media(self, creation_id: str, account: InstagramAccount) -> str:
        url = f"{self.BASE_URL}/{account.instagram_id}/media_publish"

        payload = {
            "creation_id": creation_id,
            "access_token": account.access_token
        }

        response = requests.post(url, data=payload)
        response.raise_for_status()

        return response.json()["id"]