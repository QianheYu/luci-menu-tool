import json
import re
from pathlib import Path
from typing import List

from LuciMenuTool.core.base import BaseParser
from LuciMenuTool.core.models import MenuEntry


class MenuDParser(BaseParser):
    def parse(self, source_path: Path) -> List[MenuEntry]:
        entries: List[MenuEntry] = []
        try:
            with open(source_path, "r", encoding="utf-8") as f:
                content = f.read()
                # Remove comments (// style)
                content = re.sub(r'//.*', '', content)
                # Remove trailing commas before closing brackets/braces
                content = re.sub(r',\s*([}\]])', r'', content)
                data = json.loads(content)
        except (json.JSONDecodeError, OSError):
            return entries

        for path, value in data.items():
            if not isinstance(value, dict):
                continue

            title = value.get("title", "")
            order = value.get("order", "")
            alias = ""
            action = value.get("action", {})
            if isinstance(action, dict) and action.get("type") == "alias":
                alias = action.get("path", "")

            entries.append(
                MenuEntry(
                    path=path,
                    title=title if title else None,
                    order=str(order) if order != "" else None,
                    alias=alias if alias else None,
                    metadata={"source_file": str(source_path)},
                )
            )

        return entries
