import requests
from domain.entities import Reel
from domain.repositories import InstagramPublisher


class InstagramGraphApiClient(InstagramPublisher):

    BASE_URL = "https://graph.facebook.com/v25.0"

    def __init__(self, access_token: str, ig_user_id: str):
        self.access_token = access_token
        self.ig_user_id = ig_user_id

    def publish_reel(self, reel: Reel) -> str:
        creation_id = self._create_media_container(reel)
        return self._publish_media(creation_id)

    def _create_media_container(self, reel: Reel) -> str:
        url = f"{self.BASE_URL}/{self.ig_user_id}/media"

        payload = {
            "media_type": "REELS",
            "video_url": reel.video_url,
            "caption": reel.caption,
            "access_token": self.access_token
        }

        if reel.thumbnail_url:
            payload["thumb_offset"] = 0  # можно расширить

        response = requests.post(url, data=payload)
        response.raise_for_status()

        return response.json()["id"]

    def _publish_media(self, creation_id: str) -> str:
        url = f"{self.BASE_URL}/{self.ig_user_id}/media_publish"

        payload = {
            "creation_id": creation_id,
            "access_token": self.access_token
        }

        response = requests.post(url, data=payload)
        response.raise_for_status()

        return response.json()["id"]