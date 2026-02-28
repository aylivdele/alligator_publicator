# domain/services.py

from abc import ABC, abstractmethod
from typing import Callable, List


class UniqueReelGenerator(ABC):

    @abstractmethod
    def generate(self, input_path: str, copies: int, on_generate: Callable[[str], str]) -> List[str]:
        """
        Возвращает список путей к сгенерированным видео
        """
        pass