import zoneinfo
from datetime import datetime

import requests

from app.domain.entities import GroupType, Reel, SocialType, UserGroup
from app.domain.repositories import CombinedPublisher

zn = zoneinfo.ZoneInfo("Europe/Moscow")


class SmmboxApiClient(CombinedPublisher):

    BASE_URL = "https://smmbox.com/api/v1"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def _get_default_headers(self):
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

    def publish_reel(self, reel: Reel, groups: list[UserGroup]):
        url = f"{self.BASE_URL}/posts/postpone"

        now_ts = int(datetime.now(zn).timestamp())

        attachments = []
        if reel.caption:
            attachments.append({"type": "text", "text": reel.caption})
        attachments.append({"type": "video", "url": reel.video_url, "title": reel.title})

        posts = []
        for group in groups:
            post: dict = {
                "date": now_ts + 60,
                "group": {
                    "id": group.id,
                    "social": group.social.value,
                    "type": group.type.value,
                },
                "attachments": attachments,
                "options": ["reels"],
            }
            posts.append(post)

        response = requests.post(url, json={"posts": posts}, headers=self._get_default_headers())
        response.raise_for_status()

        data = response.json()
        if not data.get("success"):
            raise Exception(f"SMMBox publish_reel failed: {data}")

    def get_user_groups(self) -> list[UserGroup]:
        url = f"{self.BASE_URL}/groups"

        response = requests.get(url, headers=self._get_default_headers())
        response.raise_for_status()

        data = response.json()
        if not data.get("success") or not data.get("response"):
            raise Exception(f"Could not get user groups: {data}")

        return [
            UserGroup(
                id=str(g["id"]),
                type=GroupType(g.get("type", "unknown")),
                social=SocialType(g.get("social", "unknown")),
                name=g.get("name", ""),
            )
            for g in data["response"]
        ]
