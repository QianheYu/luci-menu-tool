from pathlib import Path
from typing import List, Tuple, Optional

from lark import Lark, Token, Tree
from lark.exceptions import LarkError

from LuciMenuTool.core.base import BaseApplier
from LuciMenuTool.core.models import Change
from LuciMenuTool.ucode_controller.parser import UCODE_GRAMMAR


class UCodeControllerApplier(BaseApplier):
    def __init__(self):
        try:
            self._parser = Lark(UCODE_GRAMMAR, parser='earley', propagate_positions=True)
        except LarkError:
            self._parser = None

    def apply(self, source_path: Path, changes: List[Change]) -> None:
        try:
            content = source_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return

        if self._parser is None:
            return

        try:
            tree = self._parser.parse(content)
        except LarkError:
            return

        edits: List[Tuple[int, int, str]] = []

        for stmt in tree.find_data("entry_stmt"):
            children = list(stmt.children)
            if len(children) < 1:
                continue

            # Extract current path from the array
            path_tree = children[0]
            if path_tree.data != "array":
                continue

            path_parts = []
            for token in path_tree.children:
                if isinstance(token, Token):
                    if token.type == "STRING":
                        s = str(token)
                        if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
                            path_parts.append(s[1:-1])
                        else:
                            path_parts.append(s)

            current_path = "/".join(path_parts)

            # Find matching change
            matching_change = None
            for change in changes:
                if change.old_path == current_path:
                    matching_change = change
                    break

            if not matching_change:
                continue

            if not matching_change.new_path and not matching_change.new_alias:
                continue

            # Get full entry statement position from source
            meta = stmt.meta
            if not meta or not meta.line or not meta.end_line:
                continue

            # Convert line/col to char offset
            lines = content.split('\n')
            stmt_start = sum(len(l) + 1 for l in lines[:meta.line - 1]) + (meta.column - 1)
            stmt_end = sum(len(l) + 1 for l in lines[:meta.end_line - 1]) + (meta.end_column - 1)

            original_text = content[stmt_start:stmt_end]

            # Make targeted replacements in the original text
            result = original_text

            if matching_change.new_path:
                # Replace path elements in the array
                new_parts = matching_change.new_path.split("/")
                for i, token in enumerate(path_tree.children):
                    if isinstance(token, Token) and token.type == "STRING" and i < len(new_parts):
                        token_start = sum(len(l) + 1 for l in lines[:token.line - 1]) + (token.column - 1) - stmt_start
                        token_end = sum(len(l) + 1 for l in lines[:token.end_line - 1]) + (token.end_column - 1) - stmt_start
                        new_str = f'"{new_parts[i]}"'
                        result = result[:token_start] + new_str + result[token_end:]

            if matching_change.new_alias and len(children) >= 2:
                target_tree = children[1]
                for call_tree in target_tree.find_data("func_call"):
                    for child in call_tree.children:
                        if isinstance(child, Token) and child.type == "NAME" and str(child) == "alias":
                            # Find the alias array and replace it
                            for arr in call_tree.find_data("array"):
                                arr_meta = arr.meta
                                if arr_meta:
                                    arr_start = sum(len(l) + 1 for l in lines[:arr_meta.line - 1]) + (arr_meta.column - 1) - stmt_start
                                    arr_end = sum(len(l) + 1 for l in lines[:arr_meta.end_line - 1]) + (arr_meta.end_column - 1) - stmt_start
                                    new_alias_parts = matching_change.new_alias.split("/")
                                    new_arr = "[" + ", ".join([f'"{p}"' for p in new_alias_parts]) + "]"
                                    result = result[:arr_start] + new_arr + result[arr_end:]

            if result != original_text:
                edits.append((stmt_start, stmt_end, result))

        if not edits:
            return

        # Apply edits in reverse order
        edits.sort(key=lambda x: x[0], reverse=True)
        for start, end, replacement in edits:
            content = content[:start] + replacement + content[end:]

        source_path.write_text(content, encoding="utf-8")
