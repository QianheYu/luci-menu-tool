from pathlib import Path
from typing import List, Dict, Optional

from lark import Lark, Token, Tree
from lark.exceptions import LarkError

from LuciMenuTool.core.base import BaseParser
from LuciMenuTool.core.models import MenuEntry


# Lark grammar for UCode entry() calls.
# Intentionally permissive: skip everything except entry() calls.
UCODE_GRAMMAR = r"""
    start: _item*

    _item: entry_stmt | _other

    entry_stmt: "entry" "(" array "," target "," title "," order ")" ";"?
              | "entry" "(" array "," target "," title ")" ";"?
              | "entry" "(" array "," target ")" ";"?

    array: "[" [_array_item ("," _array_item)*] "]"
    _array_item: STRING | NAME

    target: func_call
    func_call: NAME "(" _func_args? ")"
    _func_args: _func_arg ("," _func_arg)*
    _func_arg: STRING | NUMBER | NAME | func_call | array

    title: func_call | STRING | "null" | "nil"
    order: NUMBER

    NAME: /[a-zA-Z_]\w*/
    STRING: /\"(?:[^\"\\]|\\.)*\"/ | /'(?:[^'\\]|\\.)*'/
    NUMBER: /\-?[0-9]+/

    _other: /[^e]+/s | /e(?!ntry\s*\()/s

    %import common.WS
    %ignore WS
    COMMENT: /\/\/[^\n]*/
    BLOCK_COMMENT: /\/\*[\s\S]*?\*\//
    %ignore COMMENT
    %ignore BLOCK_COMMENT
"""


class UCodeControllerParser(BaseParser):
    def __init__(self):
        try:
            self._parser = Lark(UCODE_GRAMMAR, parser='earley', propagate_positions=True)
        except LarkError:
            self._parser = None

    def parse(self, source_path: Path) -> List[MenuEntry]:
        try:
            content = source_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return []

        if self._parser is None:
            return []

        try:
            tree = self._parser.parse(content)
        except LarkError:
            return []

        entries: List[MenuEntry] = []
        variables = self._extract_variables(content)

        for stmt in tree.find_data("entry_stmt"):
            entry = self._process_entry_stmt(stmt, variables, str(source_path))
            if entry:
                entries.append(entry)

        return entries

    def _extract_variables(self, content: str) -> Dict[str, str]:
        """Extract let/const variable assignments."""
        import re
        variables: Dict[str, str] = {}
        for match in re.finditer(r'(?:let|const)\s+(\w+)\s*=\s*["\']([^"\']+)["\']', content):
            variables[match.group(1)] = match.group(2)
        return variables

    def _process_entry_stmt(self, stmt: Tree, variables: Dict[str, str], source_file: str) -> Optional[MenuEntry]:
        children = list(stmt.children)
        if len(children) < 1:
            return None

        # First child is the path array
        path_tree = children[0]
        if path_tree.data != "array":
            return None

        path_parts = []
        for token in path_tree.children:
            if isinstance(token, Token):
                if token.type == "STRING":
                    path_parts.append(self._unquote(token))
                elif token.type == "NAME":
                    val = variables.get(str(token))
                    if val:
                        path_parts.append(val)
                    else:
                        return None

        if not path_parts:
            return None

        full_path = "/".join(path_parts)
        entry = MenuEntry(path=full_path, metadata={
            "source_file": source_file,
            "line": stmt.meta.line if hasattr(stmt, 'meta') and stmt.meta else None,
            "col": stmt.meta.column if hasattr(stmt, 'meta') and stmt.meta else None,
            "end_line": stmt.meta.end_line if hasattr(stmt, 'meta') and stmt.meta else None,
            "end_col": stmt.meta.end_column if hasattr(stmt, 'meta') and stmt.meta else None,
        })

        # Extract alias from target (2nd child)
        if len(children) >= 2:
            target_tree = children[1]
            entry.alias = self._extract_alias(target_tree, variables)

        # Extract title (3rd child)
        if len(children) >= 3:
            title_tree = children[2]
            entry.title = self._extract_title(title_tree)

        # Extract order (4th child)
        if len(children) >= 4:
            order_tree = children[3]
            entry.order = self._extract_order(order_tree)

        return entry

    def _unquote(self, token: Token) -> str:
        s = str(token)
        if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
            return s[1:-1]
        return s

    def _extract_alias(self, target_tree: Tree, variables: Dict[str, str]) -> Optional[str]:
        if target_tree.data != "target":
            return None

        for call_tree in target_tree.find_data("func_call"):
            func_name = None
            for child in call_tree.children:
                if isinstance(child, Token) and child.type == "NAME":
                    func_name = str(child)
                    break

            if func_name != "alias":
                return None

            alias_parts = []
            for child in call_tree.children:
                if isinstance(child, Tree) and child.data == "array":
                    for token in child.children:
                        if isinstance(token, Token):
                            if token.type == "STRING":
                                alias_parts.append(self._unquote(token))
                            elif token.type == "NAME":
                                val = variables.get(str(token))
                                if val:
                                    alias_parts.append(val)
                elif isinstance(child, Token):
                    if child.type == "STRING":
                        alias_parts.append(self._unquote(child))
                    elif child.type == "NAME" and str(child) != "alias":
                        val = variables.get(str(child))
                        if val:
                            alias_parts.append(val)

            return "/".join(alias_parts) if alias_parts else None

        return None

    def _extract_title(self, title_tree: Tree) -> Optional[str]:
        if title_tree.data != "title":
            return None

        for child in title_tree.children:
            if isinstance(child, Token):
                if child.type == "STRING":
                    return self._unquote(child)
                elif str(child) in ("null", "nil"):
                    return None
            elif isinstance(child, Tree) and child.data == "func_call":
                # Handle _("title") or translate("title")
                for inner in child.children:
                    if isinstance(inner, Token) and inner.type == "STRING":
                        return self._unquote(inner)

        return None

    def _extract_order(self, order_tree: Tree) -> Optional[str]:
        if order_tree.data != "order":
            return None

        for child in order_tree.children:
            if isinstance(child, Token) and child.type == "NUMBER":
                return str(child)

        return None
