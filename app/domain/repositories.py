from abc import ABC, abstractmethod
from app.domain.models import InstagramAccount
from domain.entities import Reel, UserGroup


class InstagramPublisher(ABC):

    @abstractmethod
    def publish_reel(self, reel: Reel, account: InstagramAccount) -> str:
        """
        Публикует Reel.
        Возвращает ID опубликованного поста.
        """
        pass
    
class CombinedPublisher(ABC):

    @abstractmethod
    def publish_reel(self, reel: Reel, groups: list[UserGroup]):
        """
        Публикует Reel.
        """
        pass
    
    @abstractmethod
    def get_user_groups(self) -> list[UserGroup]:
        """
        Получает список зарегестрированных аккаунтов
        """
        pass