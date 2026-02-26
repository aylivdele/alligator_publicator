import requests
from domain.entities import Reel
from domain.repositories import InstagramPublisher



class InstagramGraphApiClient(InstagramPublisher):

    BASE_URL = "https://smmbox.com/api/v1"

    def __init__(self, api_key: str):
        self.api_key = api_key
    
    def _get_default_headers(self):
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

    def publish_reel(self, reel: Reel, group_id: str) -> str:
        raise NotImplementedError()
    
    def get_user_groups(self):
        url = f"{self.BASE_URL}/groups"

        response = requests.get(url, headers=self._get_default_headers())
        response.raise_for_status()

        json = response.json()

        if json["success"] != True or not json["response"]:
            raise Exception("Could not get user groups", json)
        
        return json["response"]

