#!/usr/bin/env python3
"""
验证模块 - 在应用前检查修改是否合理
"""

from typing import List, Dict, Tuple, Optional
from pathlib import Path
from LuciMenuTool.core.models import Change
from LuciMenuTool.core.logger import get_logger


class ValidationResult:
    """验证结果"""
    def __init__(self, is_valid: bool, errors: List[str] = None, warnings: List[str] = None):
        self.is_valid = is_valid
        self.errors = errors or []
        self.warnings = warnings or []

    def add_error(self, error: str):
        """添加错误"""
        self.errors.append(error)
        self.is_valid = False

    def add_warning(self, warning: str):
        """添加警告"""
        self.warnings.append(warning)

    def has_issues(self) -> bool:
        """是否有问题（错误或警告）"""
        return len(self.errors) > 0 or len(self.warnings) > 0


class Validator:
    """验证器，用于验证修改的合理性"""

    def __init__(self, logger=None):
        """初始化验证器

        Args:
            logger: 日志记录器
        """
        self.logger = logger or get_logger()

    def validate_changes(self, changes: List[Change], existing_paths: List[str] = None) -> ValidationResult:
        """验证修改列表

        Args:
            changes: 修改列表
            existing_paths: 已存在的路径列表（用于检测路径冲突）

        Returns:
            ValidationResult 验证结果
        """
        result = ValidationResult(True)

        if not changes:
            result.add_warning("没有需要应用的修改")
            return result

        # 检查路径冲突
        if existing_paths:
            path_conflicts = self._check_path_conflicts(changes, existing_paths)
            for conflict in path_conflicts:
                result.add_error(conflict)

        # 检查每个修改的合理性
        for i, change in enumerate(changes):
            change_result = self._validate_single_change(change, i)
            result.errors.extend(change_result.errors)
            result.warnings.extend(change_result.warnings)
            if not change_result.is_valid:
                result.is_valid = False

        return result

    def _check_path_conflicts(self, changes: List[Change], existing_paths: List[str]) -> List[str]:
        """检查路径冲突

        Args:
            changes: 修改列表
            existing_paths: 已存在的路径列表

        Returns:
            冲突信息列表
        """
        conflicts = []
        existing_set = set(existing_paths)

        for change in changes:
            if change.new_path:
                # 检查新路径是否已存在
                if change.new_path in existing_set and change.new_path != change.old_path:
                    conflicts.append(
                        f"路径冲突: 新路径 '{change.new_path}' 已存在 "
                        f"(原路径: '{change.old_path}')"
                    )

                # 检查新路径是否是其他路径的父路径
                for existing in existing_set:
                    if existing != change.new_path and existing.startswith(change.new_path + "/"):
                        conflicts.append(
                            f"路径冲突: 新路径 '{change.new_path}' 是已存在路径 '{existing}' 的父路径 "
                            f"(原路径: '{change.old_path}')"
                        )

        return conflicts

    def _validate_single_change(self, change: Change, index: int) -> ValidationResult:
        """验证单个修改

        Args:
            change: 修改对象
            index: 修改在列表中的索引

        Returns:
            ValidationResult 验证结果
        """
        result = ValidationResult(True)
        prefix = f"修改 #{index + 1} ({change.old_path})"

        # 检查原路径是否为空
        if not change.old_path:
            result.add_error(f"{prefix}: 原路径不能为空")

        # 检查路径格式
        if change.new_path:
            if not self._is_valid_path(change.new_path):
                result.add_error(f"{prefix}: 新路径格式无效 '{change.new_path}'")

            # 检查路径是否以 / 开头
            if not change.new_path.startswith("admin/"):
                result.add_warning(f"{prefix}: 新路径不以 'admin/' 开头 '{change.new_path}'")

        # 检查标题
        if change.new_title is not None:
            if not change.new_title.strip():
                result.add_error(f"{prefix}: 标题不能为空")

        # 检查排序值
        if change.new_order is not None:
            # 尝试将字符串转换为整数
            order_value = change.new_order
            if isinstance(order_value, str):
                try:
                    order_value = int(order_value)
                    # 自动更新 change 对象的值为整数
                    change.new_order = order_value
                except (ValueError, TypeError):
                    result.add_error(f"{prefix}: 排序值必须是整数，当前为 '{change.new_order}' (无法转换)")
                    return result

            if not isinstance(order_value, int):
                result.add_error(f"{prefix}: 排序值必须是整数，当前为 {type(change.new_order)}")
            elif order_value < 0:
                result.add_warning(f"{prefix}: 排序值为负数 '{order_value}'")

        # 检查别名
        if change.new_alias:
            if not self._is_valid_path(change.new_alias):
                result.add_error(f"{prefix}: 别名格式无效 '{change.new_alias}'")

        return result

    def _is_valid_path(self, path: str) -> bool:
        """检查路径格式是否有效

        Args:
            path: 路径字符串

        Returns:
            是否有效
        """
        if not path:
            return False

        # 检查是否包含空格
        if " " in path:
            return False

        # 检查是否包含特殊字符（除了 / 和 - 和 _）
        import re
        if re.search(r'[^a-zA-Z0-9_\-/]', path):
            return False

        # 检查是否以 / 开头或结尾（不应该）
        if path.startswith("/") or path.endswith("/"):
            return False

        # 检查是否包含连续的 /
        if "//" in path:
            return False

        return True

    def validate_file_before_apply(self, file_path: Path, changes: List[Change]) -> ValidationResult:
        """在应用修改前验证文件

        Args:
            file_path: 文件路径
            changes: 修改列表

        Returns:
            ValidationResult 验证结果
        """
        result = ValidationResult(True)

        # 检查文件是否存在
        if not file_path.exists():
            result.add_error(f"文件不存在: {file_path}")
            return result

        # 检查文件是否可读
        if not file_path.is_file():
            result.add_error(f"不是有效的文件: {file_path}")
            return result

        # 检查文件大小
        file_size = file_path.stat().st_size
        if file_size == 0:
            result.add_warning(f"文件为空: {file_path}")
        elif file_size > 10 * 1024 * 1024:  # 10MB
            result.add_warning(f"文件过大 ({file_size / 1024 / 1024:.2f}MB): {file_path}")

        # 检查修改数量
        if len(changes) > 100:
            result.add_warning(f"修改数量过多 ({len(changes)} 个): {file_path}")

        return result
