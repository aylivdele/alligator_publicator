from domain.entities import Reel
from domain.repositories import InstagramPublisher


class PublishReelUseCase:

    def __init__(self, publisher: InstagramPublisher):
        self.publisher = publisher

    def execute(self, video_url: str, caption: str, thumbnail_url: str | None = None) -> str:
        reel = Reel(
            video_url=video_url,
            caption=caption,
            thumbnail_url=thumbnail_url
        )
        return self.publisher.publish_reel(reel)