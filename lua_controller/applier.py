from pathlib import Path
from typing import List, Tuple, Optional, Dict

from luaparser import ast
from luaparser.astnodes import (
    Call, Name, Table, String, Number, Field, UMinusOp, LocalAssign, Assign
)

from LuciMenuTool.core.base import BaseApplier
from LuciMenuTool.core.models import Change


class LuaControllerApplier(BaseApplier):
    def apply(self, source_path: Path, changes: List[Change]) -> None:
        try:
            content = source_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return

        try:
            tree = ast.parse(content)
        except Exception:
            return

        variables = self._extract_variables(tree)
        # Store on self so _generate_new_entry_code can access it
        self._variables = variables

        # Expand path changes: cascade root path renames to all child entries
        expanded_changes = self._expand_path_changes(changes, tree, variables)

        edits: List[Tuple[int, int, str]] = []

        for node in ast.walk(tree):
            if isinstance(node, Call) and isinstance(node.func, Name):
                if node.func.id == "entry":
                    edits.extend(self._find_entry_edits(content, node, expanded_changes, variables))
                elif node.func.id == "node":
                    edits.extend(self._find_node_edits(content, node, expanded_changes))

        if not edits:
            return

        edits.sort(key=lambda x: x[0], reverse=True)
        for start, end, replacement in edits:
            content = content[:start] + replacement + content[end:]

        source_path.write_text(content, encoding="utf-8")

    def _expand_path_changes(self, changes: List[Change], tree, variables: Dict[str, str]) -> List[Change]:
        """For each change that renames a path, cascade to all child entries sharing the old prefix."""
        # Collect all fully-resolvable entry paths present in the file
        all_file_paths: set = set()
        for node in ast.walk(tree):
            if isinstance(node, Call) and isinstance(node.func, Name) and node.func.id == "entry":
                if node.args and isinstance(node.args[0], Table):
                    parts = []
                    ok = True
                    for field in node.args[0].fields:
                        val = field.value if isinstance(field, Field) else field
                        if isinstance(val, String):
                            s = val.s
                            if isinstance(s, bytes):
                                s = s.decode("utf-8", errors="ignore")
                            parts.append(s)
                        elif isinstance(val, Name) and val.id in variables:
                            parts.append(variables[val.id])
                        else:
                            ok = False
                            break
                    if ok and parts:
                        all_file_paths.add("/".join(parts))

        expanded = list(changes)
        for change in changes:
            if not change.new_path:
                continue
            old_prefix = change.old_path + "/"
            new_prefix = change.new_path + "/"
            for file_path in all_file_paths:
                if file_path.startswith(old_prefix):
                    child_new_path = new_prefix + file_path[len(old_prefix):]
                    if not any(c.old_path == file_path for c in changes):
                        expanded.append(Change(old_path=file_path, new_path=child_new_path))
        return expanded

    def _extract_variables(self, tree) -> Dict[str, str]:
        """Extract simple string variable assignments from AST."""
        variables: Dict[str, str] = {}
        for node in ast.walk(tree):
            if isinstance(node, (LocalAssign, Assign)):
                for i, target in enumerate(node.targets):
                    if isinstance(target, Name) and i < len(node.values):
                        val = node.values[i]
                        if isinstance(val, String):
                            s = val.s
                            if isinstance(s, bytes):
                                s = s.decode("utf-8", errors="ignore")
                            variables[target.id] = s
        return variables

    def _find_entry_keyword_position(self, content: str, node: Call) -> Optional[int]:
        """Find the byte offset of the 'entry' keyword for a given Call node."""
        if isinstance(node.func, Name) and node.func.first_token:
            return node.func.first_token.start

        if node.first_token:
            line_num = node.first_token.line
            lines = content.split('\n')
            if 1 <= line_num <= len(lines):
                line = lines[line_num - 1]
                line_start_pos = sum(len(l) + 1 for l in lines[:line_num - 1])
                entry_pos = line.find('entry')
                if entry_pos >= 0:
                    return line_start_pos + entry_pos

            start = node.first_token.start
            search_start = max(0, start - 200)
            prefix = content[search_start:start]
            entry_pos = prefix.rfind('entry')
            if entry_pos >= 0:
                return search_start + entry_pos

        return None

    def _find_entry_edits(self, content: str, node: Call, changes: List[Change], variables: Dict[str, str]) -> List[Tuple[int, int, str]]:
        import re
        edits: List[Tuple[int, int, str]] = []

        if len(node.args) < 1:
            return edits

        path_arg = node.args[0]
        if not isinstance(path_arg, Table):
            return edits

        # Resolve path — bail if any token is unresolvable (e.g. concat expressions)
        path_parts = []
        for field in path_arg.fields:
            val = field.value if isinstance(field, Field) else field
            if isinstance(val, String):
                s = val.s
                if isinstance(s, bytes):
                    s = s.decode("utf-8", errors="ignore")
                path_parts.append(s)
            elif isinstance(val, Name) and val.id in variables:
                path_parts.append(variables[val.id])
            else:
                return edits  # unresolvable token (concat, etc.) — skip

        current_path = "/".join(path_parts)

        matching_change = next((c for c in changes if c.old_path == current_path), None)
        if not matching_change:
            return edits

        ft = node.first_token
        lt = node.last_token
        if not ft or not lt:
            return edits

        entry_pos = self._find_entry_keyword_position(content, node)
        if entry_pos is None:
            entry_pos = ft.start

        new_code = self._generate_new_entry_code(content, node, matching_change, entry_pos, variables)
        if new_code:
            edits.append((entry_pos, lt.stop + 1, new_code))

        # Check if this entry is assigned to a variable (e.g., local page = entry(...))
        # If so, look for separate order assignment statements (e.g., page.order = 10)
        if ft:
            lines = content.split("\n")
            node_line = ft.line
            if 0 < node_line <= len(lines):
                current_line = lines[node_line - 1]
                assign_match = re.search(r'(?:local\s+)?(\w+)\s*=\s*entry\s*\(', current_line)
                if assign_match and matching_change.new_order is not None:
                    var_name = assign_match.group(1)
                    # Search for order assignment statement for this variable
                    for i, line in enumerate(lines):
                        m = re.search(rf'({var_name}\.order\s*=\s*)(-?\d+)', line)
                        if m:
                            line_offset = sum(len(l) + 1 for l in lines[:i])
                            edits.append((line_offset + m.start(2), line_offset + m.end(2), str(matching_change.new_order)))
                            break

        return edits

    def _generate_new_entry_code(self, content: str, node: Call, change: Change, entry_pos: int, variables: Dict[str, str]) -> Optional[str]:
        """Generate replacement text for an entry() call using precise token positions."""
        lt = node.last_token
        if not lt:
            return None

        original_text = content[entry_pos:lt.stop + 1]

        if not change.new_path and not change.new_alias and change.new_title is None and change.new_order is None:
            return original_text

        local_edits: List[Tuple[int, int, str]] = []

        # Update path tokens inside the Table arg
        if change.new_path:
            path_arg = node.args[0]
            if isinstance(path_arg, Table):
                new_parts = change.new_path.split("/")
                for i, field in enumerate(path_arg.fields):
                    val = field.value if isinstance(field, Field) else field
                    if i >= len(new_parts):
                        break
                    if isinstance(val, String):
                        if val.first_token and val.last_token:
                            rel_start = val.first_token.start - entry_pos
                            rel_end = val.last_token.stop + 1 - entry_pos
                            local_edits.append((rel_start, rel_end, f'"{new_parts[i]}"'))
                    elif isinstance(val, Name) and val.id in variables:
                        # Replace variable name token with new string literal
                        if val.first_token and val.last_token:
                            rel_start = val.first_token.start - entry_pos
                            rel_end = val.last_token.stop + 1 - entry_pos
                            local_edits.append((rel_start, rel_end, f'"{new_parts[i]}"'))
                    # Skip concat/other expressions — they can't be safely replaced

        # Update alias
        if change.new_alias and len(node.args) >= 2:
            target_node = node.args[1]
            if isinstance(target_node, Call) and isinstance(target_node.func, Name) and target_node.func.id == "alias":
                new_alias_parts = change.new_alias.split("/")
                new_alias_str = ", ".join([f'"{p}"' for p in new_alias_parts])
                if target_node.first_token and target_node.last_token:
                    rel_start = target_node.first_token.start - entry_pos
                    rel_end = target_node.last_token.stop + 1 - entry_pos
                    local_edits.append((rel_start, rel_end, f'alias({new_alias_str})'))

        # Update title (3rd arg)
        if change.new_title is not None and len(node.args) >= 3:
            title_node = node.args[2]
            if title_node.first_token and title_node.last_token:
                rel_start = title_node.first_token.start - entry_pos
                rel_end = title_node.last_token.stop + 1 - entry_pos
                local_edits.append((rel_start, rel_end, f'_("{change.new_title}")'))

        # Update order (4th arg)
        if change.new_order is not None and len(node.args) >= 4:
            order_node = node.args[3]
            if order_node.first_token and order_node.last_token:
                rel_start = order_node.first_token.start - entry_pos
                rel_end = order_node.last_token.stop + 1 - entry_pos
                local_edits.append((rel_start, rel_end, str(change.new_order)))

        if not local_edits:
            return original_text

        result = original_text
        local_edits.sort(key=lambda x: x[0], reverse=True)
        for rel_start, rel_end, replacement in local_edits:
            result = result[:rel_start] + replacement + result[rel_end:]

        return result

    def _find_node_edits(self, content: str, node: Call, changes: List[Change]) -> List[Tuple[int, int, str]]:
        import re
        edits: List[Tuple[int, int, str]] = []

        path_parts = []
        for arg in node.args:
            if isinstance(arg, String):
                s = arg.s
                if isinstance(s, bytes):
                    s = s.decode("utf-8", errors="ignore")
                path_parts.append(s)

        current_path = "/".join(path_parts)
        matching_change = next((c for c in changes if c.old_path == current_path), None)
        if not matching_change:
            return edits

        ft = node.first_token
        if not ft:
            return edits

        lines = content.split("\n")
        node_line = ft.line
        if not (0 < node_line <= len(lines)):
            return edits

        current_line = lines[node_line - 1]
        assign_match = re.search(r'(?:local\s+)?(\w+)\s*=\s*node\s*\(', current_line)
        if not assign_match:
            return edits

        var_name = assign_match.group(1)

        if matching_change.new_path:
            new_args = ", ".join([f'"{p}"' for p in matching_change.new_path.split("/")])
            node_lt = node.last_token
            if node_lt:
                line_start = ft.start - (ft.column - 1)
                edits.append((line_start, node_lt.stop + 1, f'{var_name} = node({new_args})'))

        if matching_change.new_title is not None:
            for i, line in enumerate(lines):
                m = re.search(rf'{var_name}\.title\s*=\s*_\(\s*"([^"]+)"\s*\)', line)
                if m:
                    line_offset = sum(len(l) + 1 for l in lines[:i])
                    inner_m = re.search(r'_\(\s*"([^"]+)"\s*\)', m.group(0))
                    if inner_m:
                        edits.append((line_offset + m.start(0) + inner_m.start(1),
                                      line_offset + m.start(0) + inner_m.end(1),
                                      matching_change.new_title))
                    break
                m2 = re.search(rf'{var_name}\.title\s*=\s*"([^"]+)"', line)
                if m2:
                    line_offset = sum(len(l) + 1 for l in lines[:i])
                    edits.append((line_offset + m2.start(1), line_offset + m2.end(1), matching_change.new_title))
                    break

        if matching_change.new_order is not None:
            for i, line in enumerate(lines):
                m = re.search(rf'({var_name}\.order\s*=\s*)(-?\d+)', line)
                if m:
                    line_offset = sum(len(l) + 1 for l in lines[:i])
                    edits.append((line_offset + m.start(2), line_offset + m.end(2), str(matching_change.new_order)))
                    break

        return edits
