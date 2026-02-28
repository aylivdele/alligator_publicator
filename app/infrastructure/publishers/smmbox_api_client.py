from datetime import datetime, time
import zoneinfo

import requests
from app.domain.entities import Reel, UserGroup
from app.domain.repositories import CombinedPublisher

zn = zoneinfo.ZoneInfo("Europe/Moscow")

class InstagramGraphApiClient(CombinedPublisher):

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

        date = (datetime.now(zn) - datetime(1970,1,1)).total_seconds()

        posts = [{
            "date": date,
            "group": group
        } for group in groups]

        response = requests.post(url, headers=self._get_default_headers())
        response.raise_for_status()

        json = response.json()

        if json["success"] != True:
            raise Exception("Could not get user groups", json)
        
    
    def get_user_groups(self) -> list[UserGroup]:
        url = f"{self.BASE_URL}/groups"

        response = requests.get(url, headers=self._get_default_headers())
        response.raise_for_status()

        json = response.json()

        if json["success"] != True or not json["response"]:
            raise Exception("Could not get user groups", json)
        
        return json["response"]

