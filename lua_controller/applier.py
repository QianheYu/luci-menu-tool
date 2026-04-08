import re
from pathlib import Path
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass

from luaparser import ast
from luaparser.astnodes import (
    Call, Name, Table, String, Number, Field, UMinusOp, LocalAssign, Assign, 
    BinaryOp, Concat
)

from LuciMenuTool.core.base import BaseApplier
from LuciMenuTool.core.models import Change


@dataclass
class EntryInfo:
    """Entry 信息，用于精确定位"""
    node: Call
    path: str
    line: int
    column: int
    var_name: Optional[str] = None
    is_resolvable: bool = True


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

        # 收集所有 entry 信息，用于更精确的匹配
        entries_info = self._collect_entries_info(tree, variables, content)

        # Expand path changes: cascade root path renames to all child entries
        expanded_changes = self._expand_path_changes(changes, entries_info)

        edits: List[Tuple[int, int, str]] = []

        for node in ast.walk(tree):
            if isinstance(node, Call) and isinstance(node.func, Name):
                if node.func.id == "entry":
                    edits.extend(self._find_entry_edits(content, node, expanded_changes, variables, entries_info))
                elif node.func.id == "node":
                    edits.extend(self._find_node_edits(content, node, expanded_changes))

        if not edits:
            return

        edits.sort(key=lambda x: x[0], reverse=True)
        for start, end, replacement in edits:
            content = content[:start] + replacement + content[end:]

        source_path.write_text(content, encoding="utf-8")

    def _collect_entries_info(self, tree, variables: Dict[str, str], content: str) -> Dict[str, EntryInfo]:
        """收集所有 entry 的详细信息

        Args:
            tree: AST 树
            variables: 变量字典
            content: 文件内容

        Returns:
            路径到 EntryInfo 的映射
        """
        entries_info = {}

        for node in ast.walk(tree):
            if isinstance(node, Call) and isinstance(node.func, Name) and node.func.id == "entry":
                if not node.args:
                    continue

                path_arg = node.args[0]
                if not isinstance(path_arg, Table):
                    continue

                # 尝试解析路径
                path_parts = []
                is_resolvable = True

                for field in path_arg.fields:
                    val = field.value if isinstance(field, Field) else field
                    if isinstance(val, String):
                        s = val.s
                        if isinstance(s, bytes):
                            s = s.decode("utf-8", errors="ignore")
                        path_parts.append(s)
                    elif isinstance(val, Name) and val.id in variables:
                        path_parts.append(variables[val.id])
                    elif isinstance(val, BinaryOp) and isinstance(val.op, Concat):
                        # 处理字符串拼接
                        concat_result = self._resolve_concat_expression(val, variables)
                        if concat_result:
                            path_parts.append(concat_result)
                        else:
                            is_resolvable = False
                            break
                    else:
                        is_resolvable = False
                        break

                if is_resolvable and path_parts:
                    path = "/".join(path_parts)

                    # 获取位置信息
                    line = node.first_token.line if node.first_token else 0
                    column = node.first_token.column if node.first_token else 0

                    # 检查是否被赋值给变量
                    var_name = None
                    if line > 0:
                        lines = content.split("\n")
                        if line <= len(lines):
                            current_line = lines[line - 1]
                            assign_match = re.search(r'(?:local\s+)?(\w+)\s*=\s*entry\s*\(', current_line)
                            if assign_match:
                                var_name = assign_match.group(1)

                    entries_info[path] = EntryInfo(
                        node=node,
                        path=path,
                        line=line,
                        column=column,
                        var_name=var_name,
                        is_resolvable=is_resolvable
                    )

        return entries_info

    def _resolve_concat_expression(self, node: BinaryOp, variables: Dict[str, str]) -> Optional[str]:
        """解析字符串拼接表达式

        Args:
            node: 二元操作节点
            variables: 变量字典

        Returns:
            解析后的字符串，如果无法解析则返回 None
        """
        if not isinstance(node.op, Concat):
            return None

        # 递归解析左右操作数
        left = self._resolve_value(node.left, variables)
        right = self._resolve_value(node.right, variables)

        if left is not None and right is not None:
            return left + right

        return None

    def _resolve_value(self, node, variables: Dict[str, str]) -> Optional[str]:
        """解析节点值

        Args:
            node: AST 节点
            variables: 变量字典

        Returns:
            解析后的字符串，如果无法解析则返回 None
        """
        if isinstance(node, String):
            s = node.s
            if isinstance(s, bytes):
                s = s.decode("utf-8", errors="ignore")
            return s
        elif isinstance(node, Name) and node.id in variables:
            return variables[node.id]
        elif isinstance(node, BinaryOp) and isinstance(node.op, Concat):
            return self._resolve_concat_expression(node, variables)

        return None

    def _expand_path_changes(self, changes: List[Change], entries_info: Dict[str, EntryInfo]) -> List[Change]:
        """For each change that renames a path, cascade to all child entries sharing the old prefix."""
        all_file_paths = set(entries_info.keys())

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

    def _find_entry_edits(self, content: str, node: Call, changes: List[Change], 
                         variables: Dict[str, str], entries_info: Dict[str, EntryInfo]) -> List[Tuple[int, int, str]]:
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
            elif isinstance(val, BinaryOp) and isinstance(val.op, Concat):
                # 处理字符串拼接
                concat_result = self._resolve_concat_expression(val, variables)
                if concat_result:
                    path_parts.append(concat_result)
                else:
                    return edits  # unresolvable token — skip
            else:
                return edits  # unresolvable token — skip

        current_path = "/".join(path_parts)

        # 使用 entries_info 进行更精确的匹配
        matching_change = None
        if current_path in entries_info:
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

        # Clean up duplicate markers in title
        if change.new_title is not None:
            change.new_title = self._clean_duplicate_markers(change.new_title)

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

    def _clean_duplicate_markers(self, title: str) -> str:
        """Remove duplicate markers from title.

        For example, if title is "Title (Modified) (Modified)",
        return "Title (Modified)".
        """
        if not title:
            return title

        # Common markers that might be duplicated
        markers = [
            r'\(Modified\)',
            r'\(已修改\)',
            r'\(Updated\)',
            r'\(已更新\)',
        ]

        # Remove duplicates for each marker
        for marker in markers:
            # If marker appears multiple times, keep only the first occurrence
            pattern = rf'({marker})\s*({marker})+'
            title = re.sub(pattern, r'\g<1>', title)

        # Remove consecutive duplicate markers
        pattern = r'(\([^)]+\))\s*\1+'
        title = re.sub(pattern, r'\g<1>', title)

        return title
