import json
import re
from pathlib import Path
from typing import List

from LuciMenuTool.core.base import BaseApplier
from LuciMenuTool.core.models import Change


class MenuDApplier(BaseApplier):
    def apply(self, source_path: Path, changes: List[Change]) -> None:
        try:
            with open(source_path, "r", encoding="utf-8") as f:
                original_content = f.read()
                data = json.loads(original_content)
        except (json.JSONDecodeError, OSError):
            return

        content = original_content
        modified = False

        for change in changes:
            if change.old_path not in data:
                continue

            entry = data[change.old_path]

            if change.new_title is not None and entry.get("title") != change.new_title:
                content = self._replace_string_value(content, change.old_path, "title", change.new_title)
                entry["title"] = change.new_title
                modified = True

            if change.new_order is not None:
                old_order = entry.get("order")
                if str(old_order) != str(change.new_order):
                    try:
                        new_order_val = int(change.new_order)
                    except (ValueError, TypeError):
                        new_order_val = change.new_order
                    content = self._replace_or_add_order(content, change.old_path, old_order, new_order_val)
                    entry["order"] = new_order_val
                    modified = True

            if change.new_alias is not None:
                action = entry.get("action", {})
                if isinstance(action, dict) and action.get("path") != change.new_alias:
                    action["type"] = "alias"
                    action["path"] = change.new_alias
                    entry["action"] = action
                    modified = True
                    content = self._full_reserialize(original_content, data)

            if change.new_path and change.new_path != change.old_path:
                key_pos = self._find_entry_key_pos(content, change.old_path)
                if key_pos != -1:
                    needle = f'"{change.old_path}"'
                    content = content[:key_pos] + f'"{change.new_path}"' + content[key_pos + len(needle):]
                data[change.new_path] = data.pop(change.old_path)
                modified = True

        if modified:
            if original_content.endswith('\n') and not content.endswith('\n'):
                content += '\n'
            with open(source_path, "w", encoding="utf-8") as f:
                f.write(content)

    def _find_matching_brace(self, content: str, open_pos: int) -> int:
        """Return position of the closing } matching the { at open_pos.
        Correctly skips over nested braces and string literals."""
        depth = 0
        in_string = False
        escape = False
        for i in range(open_pos, len(content)):
            c = content[i]
            if escape:
                escape = False
                continue
            if c == '\\' and in_string:
                escape = True
                continue
            if c == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    return i
        return -1

    def _find_entry_value_brace(self, content: str, path_pos: int) -> int:
        """Find the opening { of the entry's value object (the { after "path": ).
        Skips over any string content to find the first real { after the colon."""
        # Find the closing quote of the key
        key_start = content.find('"', path_pos)
        if key_start == -1:
            return -1
        key_end = content.find('"', key_start + 1)
        if key_end == -1:
            return -1
        # Find the colon after the key
        colon_pos = content.find(':', key_end + 1)
        if colon_pos == -1:
            return -1
        # Find the { after the colon, skipping whitespace
        i = colon_pos + 1
        while i < len(content) and content[i] in (' ', '\t', '\n', '\r'):
            i += 1
        if i < len(content) and content[i] == '{':
            return i
        return -1

    def _find_entry_key_pos(self, content: str, entry_path: str) -> int:
        """Find position of entry_path when it appears as a JSON object key.

        A key occurrence is characterised by being followed (with optional
        whitespace) by a colon and then an opening brace.  This prevents
        false matches when the same path string appears as a *value* (e.g.
        inside an "action"/"path" field).
        """
        needle = f'"{entry_path}"'
        search_from = 0
        while True:
            pos = content.find(needle, search_from)
            if pos == -1:
                return -1
            # Check that what follows is ":" then optional whitespace then "{"
            after = content[pos + len(needle):]
            stripped = after.lstrip(' \t\n\r')
            if stripped.startswith(':'):
                rest = stripped[1:].lstrip(' \t\n\r')
                if rest.startswith('{'):
                    return pos
            search_from = pos + 1
        return -1

    def _replace_string_value(self, content: str, entry_path: str, key: str, new_value: str) -> str:
        """Replace a string value for a given key inside the entry block."""
        path_pos = self._find_entry_key_pos(content, entry_path)
        if path_pos == -1:
            return content
        brace_pos = self._find_entry_value_brace(content, path_pos)
        if brace_pos == -1:
            return content
        block_end = self._find_matching_brace(content, brace_pos)
        if block_end == -1:
            return content

        key_pattern = re.compile(r'("' + re.escape(key) + r'"\s*:\s*")([^"\\]*)(")')
        match = key_pattern.search(content, brace_pos, block_end)
        if match:
            return content[:match.start(2)] + new_value + content[match.end(2):]
        return content

    def _replace_or_add_order(self, content: str, entry_path: str, old_order, new_order) -> str:
        """Replace an existing order value or insert it if missing."""
        path_pos = self._find_entry_key_pos(content, entry_path)
        if path_pos == -1:
            return content
        brace_pos = self._find_entry_value_brace(content, path_pos)
        if brace_pos == -1:
            return content
        block_end = self._find_matching_brace(content, brace_pos)
        if block_end == -1:
            return content

        if old_order is not None:
            order_pattern = re.compile(r'("order"\s*:\s*)(-?\d+)')
            match = order_pattern.search(content, brace_pos, block_end)
            if match:
                return content[:match.start(2)] + str(new_order) + content[match.end(2):]

        # Insert before the closing brace of the entry block.
        # Find the last non-whitespace char before block_end so the comma
        # attaches directly to the previous value line.
        indent = self._detect_entry_indent(content, brace_pos, block_end)
        # Detect the indentation of the closing brace itself
        close_indent = self._detect_close_indent(content, block_end)
        last_val_end = block_end
        while last_val_end > brace_pos and content[last_val_end - 1] in (' ', '\t', '\n', '\r'):
            last_val_end -= 1
        insert = f',\n{indent}"order": {new_order}\n{close_indent}'
        return content[:last_val_end] + insert + content[block_end:]

    def _detect_entry_indent(self, content: str, brace_pos: int, block_end: int) -> str:
        """Detect indentation of keys inside the entry block."""
        m = re.search(r'\n(\s+)"[^"]+":', content[brace_pos:block_end])
        if m:
            return m.group(1)
        return '        '

    def _detect_close_indent(self, content: str, close_pos: int) -> str:
        """Detect the indentation of the closing brace at close_pos."""
        line_start = content.rfind('\n', 0, close_pos)
        if line_start == -1:
            return ''
        between = content[line_start + 1:close_pos]
        if all(c in (' ', '\t') for c in between):
            return between
        return ''

    def _full_reserialize(self, original_content: str, data: dict) -> str:
        indent = self._detect_indent(original_content)
        separators = self._detect_separators(original_content)
        return json.dumps(data, indent=indent, separators=separators, ensure_ascii=False)

    def _detect_indent(self, content: str) -> str:
        match = re.search(r'^(\s+)"[^"]+":', content, re.MULTILINE)
        if match:
            indent = match.group(1)
            if '\t' in indent:
                return '\t'
            return len(indent)
        return 2

    def _detect_separators(self, content: str) -> tuple:
        if re.search(r'":\s+"', content):
            return (", ", ": ")
        return (",", ":")
