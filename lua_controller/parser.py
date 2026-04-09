import re
import sys
import os
from pathlib import Path
from typing import List, Dict, Optional

from luaparser import ast
from luaparser.astnodes import (
    Call, Name, Table, String, Number, Assign, Field, LocalAssign, UMinusOp,
    Index, Attribute
)

from LuciMenuTool.core.base import BaseParser
from LuciMenuTool.core.models import MenuEntry


def _decode(val):
    if isinstance(val, bytes):
        return val.decode("utf-8", errors="ignore")
    return val


def _suppress_antlr_errors(func):
    """Decorator to suppress ANTLR lexer error output."""
    def wrapper(*args, **kwargs):
        old_stderr = sys.stderr
        devnull = open(os.devnull, 'w')
        sys.stderr = devnull
        try:
            return func(*args, **kwargs)
        finally:
            sys.stderr = old_stderr
            devnull.close()
    return wrapper


@_suppress_antlr_errors
def _try_ast_parse(content: str):
    """Try to parse content with luaparser, suppressing errors."""
    return ast.parse(content)


class LuaControllerParser(BaseParser):
    def parse(self, source_path: Path) -> List[MenuEntry]:
        try:
            content = source_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return []

        # 预处理：移除不必要的转义字符（如 \/）
        content = re.sub(r'\\/', '/', content)

        # Try AST parsing first
        try:
            tree = _try_ast_parse(content)
            return self._parse_with_ast(tree, content, str(source_path))
        except Exception:
            # Fallback to regex-based parsing for files with syntax issues
            return self._parse_with_regex(content, str(source_path))

    def _parse_with_ast(self, tree, content: str, source_file: str) -> List[MenuEntry]:
        """Parse using luaparser AST."""
        variables: Dict[str, str] = {}
        entries: List[MenuEntry] = []
        entry_var_map: Dict[str, MenuEntry] = {}

        # Try to infer appname from source file path
        # For packages like luci-app-passwall2, appname is typically "passwall2"
        import re
        appname_match = re.search(r'luci-app-([a-zA-Z0-9_-]+)', source_file)
        if appname_match:
            variables['appname'] = appname_match.group(1)

        for node in ast.walk(tree):
            if isinstance(node, LocalAssign):
                for i, target in enumerate(node.targets):
                    if isinstance(target, Name) and i < len(node.values):
                        value = _resolve_value(node.values[i], variables)
                        if value is not None:
                            variables[target.id] = value

                        # Check if this is: local page = entry(...)
                        if isinstance(node.values[i], Call):
                            call_node = node.values[i]
                            if isinstance(call_node.func, Name) and call_node.func.id == "entry":
                                entry = _parse_entry(call_node, variables)
                                if entry:
                                    entry_var_map[target.id] = entry
                                    entries.append(entry)

            elif isinstance(node, Assign):
                for i, target in enumerate(node.targets):
                    if isinstance(target, Name) and i < len(node.values):
                        value = _resolve_value(node.values[i], variables)
                        if value is not None:
                            variables[target.id] = value

                        # Check if this is: page = entry(...)
                        if isinstance(node.values[i], Call):
                            call_node = node.values[i]
                            if isinstance(call_node.func, Name) and call_node.func.id == "entry":
                                entry = _parse_entry(call_node, variables)
                                if entry:
                                    entry_var_map[target.id] = entry
                                    entries.append(entry)

                    # Check if this is: page.order = 10 or page.title = _("...")
                    elif isinstance(target, Index):
                        if isinstance(target.value, Name) and target.value.id in entry_var_map:
                            entry = entry_var_map[target.value.id]
                            if isinstance(target.idx, Name):
                                if target.idx.id == "order" and isinstance(node.values[i], Number):
                                    entry.order = str(node.values[i].n)
                                elif target.idx.id == "order" and isinstance(node.values[i], UMinusOp):
                                    if isinstance(node.values[i].operand, Number):
                                        entry.order = str(-node.values[i].operand.n)

                    # Check if this is: page.title = _("...")
                    elif isinstance(target, Attribute):
                        if isinstance(target.value, Name) and target.value.id in entry_var_map:
                            entry = entry_var_map[target.value.id]
                            if target.attr == "order" and isinstance(node.values[i], Number):
                                entry.order = str(node.values[i].n)
                            elif target.attr == "order" and isinstance(node.values[i], UMinusOp):
                                if isinstance(node.values[i].operand, Number):
                                    entry.order = str(-node.values[i].operand.n)
                            elif target.attr == "title" and isinstance(node.values[i], Call):
                                if isinstance(node.values[i].func, Name) and node.values[i].func.id == "_":
                                    if node.values[i].args and isinstance(node.values[i].args[0], String):
                                        entry.title = _decode(node.values[i].args[0].s)
                            elif target.attr == "title" and isinstance(node.values[i], String):
                                entry.title = _decode(node.values[i].s)

            if isinstance(node, Call) and isinstance(node.func, Name):
                if node.func.id == "entry":
                    # Only add if not already added via assignment
                    entry = _parse_entry(node, variables)
                    if entry and entry.path not in [e.path for e in entries]:
                        entries.append(entry)
                elif node.func.id == "node":
                    entry = _parse_node_ast(node, variables, content)
                    if entry:
                        entries.append(entry)

        return self._deduplicate(entries)

    def _parse_with_regex(self, content: str, source_file: str) -> List[MenuEntry]:
        """Fallback regex-based parser for files that can't be parsed by luaparser."""
        entries: List[MenuEntry] = []
        variables: Dict[str, str] = {}

        # Extract variables
        for match in re.finditer(r'(?:local\s+)?(\w+)\s*=\s*["\']([^"\']+)["\']', content):
            var_name, var_value = match.group(1), match.group(2)
            if var_value and not var_value.endswith('\\'):
                variables[var_name] = var_value

        # Parse entry() calls
        for match in re.finditer(r'entry\s*\(\s*\{([^}]+)\}\s*,', content):
            path_str = match.group(1)
            if '..' in path_str:
                continue

            resolved_path = path_str
            for var_name, var_value in variables.items():
                resolved_path = re.sub(r'\b' + re.escape(var_name) + r'\b', lambda m: var_value, resolved_path)

            if 'appname' in resolved_path or '..' in resolved_path:
                continue

            parts = [p.strip().strip('"').strip("'") for p in resolved_path.split(',')]
            full_path = "/".join(parts)

            entry = MenuEntry(path=full_path, metadata={"source_file": source_file})

            # Find the scope of this entry call
            after_bracket = content[match.end() - 1:]
            depth = 1
            end_pos = -1
            for i, ch in enumerate(after_bracket):
                if ch == '(':
                    depth += 1
                elif ch == ')':
                    depth -= 1
                    if depth == 0:
                        end_pos = i
                        break

            if end_pos == -1:
                continue

            entry_scope = after_bracket[:end_pos]

            # Extract alias
            alias_match = re.search(r'alias\s*\(\s*\{([^}]+)\}', entry_scope)
            if alias_match:
                alias_path_str = alias_match.group(1)
                for var_name, var_value in variables.items():
                    alias_path_str = re.sub(r'\b' + re.escape(var_name) + r'\b', lambda m: var_value, alias_path_str)
                alias_parts = [p.strip().strip('"').strip("'") for p in alias_path_str.split(',')]
                entry.alias = "/".join(alias_parts)
            else:
                alias_match = re.search(r'alias\s*\(\s*([^)]+)\)', entry_scope)
                if alias_match:
                    alias_args = alias_match.group(1)
                    for var_name, var_value in variables.items():
                        alias_args = re.sub(r'\b' + re.escape(var_name) + r'\b', lambda m: var_value, alias_args)
                    alias_parts = [p.strip().strip('"').strip("'") for p in alias_args.split(',')]
                    entry.alias = "/".join(alias_parts)

            # Extract title
            cleaned_scope = re.sub(r'(alias|cbi|call|form|template|firstchild|arcombine)\s*\([^)]*\)', 'TARGET', entry_scope)
            title_match = re.search(r'TARGET\s*,\s*_\(\s*"([^"]+)"\s*\)', cleaned_scope)
            if not title_match:
                title_match = re.search(r'TARGET\s*,\s*"([^"]+)"', cleaned_scope)
            if not title_match:
                title_match = re.search(r',\s*_\(\s*"([^"]+)"\s*\)', entry_scope)
            if title_match and title_match.lastindex:
                entry.title = title_match.group(1)

            # Extract order
            order_match = re.search(r',\s*(-?\d+)\s*$', entry_scope)
            if order_match:
                entry.order = order_match.group(1)

            entries.append(entry)

        # Parse node() calls
        for match in re.finditer(r'(\w+)\s*=\s*node\s*\(\s*([^)]+)\)', content):
            var_name = match.group(1)
            args_str = match.group(2)
            args = [a.strip().strip('"').strip("'") for a in args_str.split(',')]
            node_path = "/".join(args)

            entry = MenuEntry(path=node_path, metadata={"source_file": source_file})

            # Find title and order
            search_start = match.end()
            next_match = re.search(r'(\w+)\s*=\s*node\s*\(', content[search_start:])
            search_end = search_start + next_match.start() if next_match else len(content)

            order_match = re.search(rf'{var_name}\.order\s*=\s*(-?\d+)', content[search_start:search_end])
            if order_match:
                entry.order = order_match.group(1)

            title_match = re.search(rf'{var_name}\.title\s*=\s*_\(\s*"([^"]+)"\s*\)', content[search_start:search_end])
            if title_match:
                entry.title = title_match.group(1)
            else:
                title_match = re.search(rf'{var_name}\.title\s*=\s*"([^"]+)"', content[search_start:search_end])
                if title_match:
                    entry.title = title_match.group(1)

            entries.append(entry)

        return self._deduplicate(entries)

    def _deduplicate(self, entries: List[MenuEntry]) -> List[MenuEntry]:
        """Deduplicate entries by path, keeping non-empty values."""
        seen: Dict[str, MenuEntry] = {}
        for entry in entries:
            if entry.path in seen:
                existing = seen[entry.path]
                if not existing.title and entry.title:
                    existing.title = entry.title
                if not existing.order and entry.order:
                    existing.order = entry.order
                if not existing.alias and entry.alias:
                    existing.alias = entry.alias
            else:
                seen[entry.path] = entry
        return list(seen.values())


def _resolve_value(node, variables: Dict[str, str]) -> Optional[str]:
    if isinstance(node, String):
        return _decode(node.s)
    elif isinstance(node, Name):
        return variables.get(node.id)
    return None


def _parse_entry(node: Call, variables: Dict[str, str]) -> Optional[MenuEntry]:
    if len(node.args) < 1:
        return None

    path_arg = node.args[0]
    if not isinstance(path_arg, Table):
        return None

    path_parts = []
    for field in path_arg.fields:
        val = field.value if isinstance(field, Field) else field
        part = _resolve_value(val, variables)
        if part is None:
            return None
        path_parts.append(part)

    if "appname" in path_parts and "appname" not in variables:
        return None

    full_path = "/".join(path_parts)
    entry = MenuEntry(path=full_path)

    if len(node.args) >= 2:
        entry.alias = _extract_alias(node.args[1], variables)

    if len(node.args) >= 3:
        entry.title = _extract_title(node.args[2])

    if len(node.args) >= 4:
        entry.order = _extract_order(node.args[3])

    return entry


def _parse_node_ast(node: Call, variables: Dict[str, str], source: str) -> Optional[MenuEntry]:
    if len(node.args) < 1:
        return None

    path_parts = []
    for arg in node.args:
        part = _resolve_value(arg, variables)
        if part is None:
            return None
        path_parts.append(part)

    full_path = "/".join(path_parts)
    entry = MenuEntry(path=full_path)

    ft = node.first_token
    node_line = ft.line if ft else None

    if node_line:
        lines = source.split("\n")
        if 0 < node_line <= len(lines):
            current_line = lines[node_line - 1]
            assign_match = re.search(r'(?:local\s+)?(\w+)\s*=\s*node\s*\(', current_line)
            if assign_match:
                var_name = assign_match.group(1)
                for line in lines:
                    m = re.search(rf'{var_name}\.title\s*=\s*_\(\s*"([^"]+)"\s*\)', line)
                    if m:
                        entry.title = m.group(1)
                    m = re.search(rf'{var_name}\.title\s*=\s*"([^"]+)"', line)
                    if m:
                        entry.title = m.group(1)
                    m = re.search(rf'{var_name}\.order\s*=\s*(-?\d+)', line)
                    if m:
                        entry.order = m.group(1)

    return entry


def _extract_alias(node, variables: Dict[str, str]) -> Optional[str]:
    if not isinstance(node, Call):
        return None
    if not isinstance(node.func, Name) or node.func.id != "alias":
        return None

    alias_parts = []
    for arg in node.args:
        if isinstance(arg, Table):
            for field in arg.fields:
                val = field.value if isinstance(field, Field) else field
                part = _resolve_value(val, variables)
                if part:
                    alias_parts.append(part)
        elif isinstance(arg, String):
            alias_parts.append(_decode(arg.s))
        elif isinstance(arg, Name):
            val = variables.get(arg.id)
            if val:
                alias_parts.append(val)

    return "/".join(alias_parts) if alias_parts else None


def _extract_title(node) -> Optional[str]:
    if isinstance(node, Call) and isinstance(node.func, Name):
        if node.func.id == "_" and node.args:
            arg = node.args[0]
            if isinstance(arg, String):
                return _decode(arg.s)
        elif node.func.id == "translate" and node.args:
            arg = node.args[0]
            if isinstance(arg, String):
                return _decode(arg.s)
    elif isinstance(node, String):
        return _decode(node.s)
    return None


def _extract_order(node) -> Optional[str]:
    if isinstance(node, Number):
        return str(node.n)
    elif isinstance(node, UMinusOp):
        if isinstance(node.operand, Number):
            return str(-node.operand.n)
    return None
