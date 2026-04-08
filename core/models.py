from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class MenuEntry:
    path: str
    title: Optional[str] = None
    order: Optional[str] = None
    alias: Optional[str] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class MenuTree:
    root: MenuEntry
    children: List[MenuEntry] = field(default_factory=list)


@dataclass
class Change:
    old_path: str
    new_path: Optional[str] = None
    new_title: Optional[str] = None
    new_order: Optional[str] = None
    new_alias: Optional[str] = None
