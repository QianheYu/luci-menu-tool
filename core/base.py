from abc import ABC, abstractmethod
from pathlib import Path
from typing import List

from LuciMenuTool.core.models import MenuEntry, Change


class BaseParser(ABC):
    @abstractmethod
    def parse(self, source_path: Path) -> List[MenuEntry]:
        pass


class BaseApplier(ABC):
    @abstractmethod
    def apply(self, source_path: Path, changes: List[Change]) -> None:
        pass
