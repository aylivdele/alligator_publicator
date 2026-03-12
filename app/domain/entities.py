from dataclasses import dataclass
from enum import Enum
from typing import Optional


@dataclass
class Reel:
    video_url: str
    caption: str
    thumbnail_url: Optional[str] = None
    is_trial: Optional[bool] = False
    title: Optional[str] = None

class GroupType(Enum):
    USER = 'user'
    GROUP = 'group'
    PAGE = 'page'
    UNKNOWN = "unknown"

    @classmethod
    def _missing_(cls, value):
        return cls.UNKNOWN

class SocialType(Enum):
    INSTAGRAM = 'io'
    VK = 'vk'
    TIKTOK = 'to'
    YOUTUBE = 'gg'
    UNKNOWN = "unknown"

    @classmethod
    def _missing_(cls, value):
        return cls.UNKNOWN

@dataclass
class UserGroup:
    id: str
    type: GroupType
    social: SocialType
    name: str
