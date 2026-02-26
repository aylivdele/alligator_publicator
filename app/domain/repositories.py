from abc import ABC, abstractmethod
from domain.entities import Reel


class InstagramPublisher(ABC):

    @abstractmethod
    def publish_reel(self, reel: Reel) -> str:
        """
        Публикует Reel.
        Возвращает ID опубликованного поста.
        """
        pass