#!/usr/bin/env python3
"""
错误处理模块 - 提供详细的错误信息和修复建议
"""

from typing import Optional, Dict, List
from enum import Enum


class ErrorType(Enum):
    """错误类型枚举"""
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    PARSE_ERROR = "PARSE_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    APPLY_ERROR = "APPLY_ERROR"
    PATH_CONFLICT = "PATH_CONFLICT"
    UNKNOWN_SOURCE = "UNKNOWN_SOURCE"
    FILE_VALIDATION_ERROR = "FILE_VALIDATION_ERROR"


class ErrorHandler:
    """错误处理器，提供详细的错误信息和修复建议"""

    # 错误信息模板
    ERROR_MESSAGES = {
        ErrorType.FILE_NOT_FOUND: {
            "description": "文件未找到",
            "suggestions": [
                "检查文件路径是否正确",
                "确认文件是否存在",
                "检查文件权限"
            ]
        },
        ErrorType.PARSE_ERROR: {
            "description": "解析错误",
            "suggestions": [
                "检查文件格式是否正确",
                "确认文件内容是否符合规范",
                "检查是否有语法错误"
            ]
        },
        ErrorType.VALIDATION_ERROR: {
            "description": "验证失败",
            "suggestions": [
                "检查修改的路径是否有效",
                "确认路径不以 'admin/' 开头",
                "检查标题是否为空",
                "检查排序值是否为整数",
                "检查别名格式是否正确"
            ]
        },
        ErrorType.APPLY_ERROR: {
            "description": "应用修改失败",
            "suggestions": [
                "检查文件是否可写",
                "确认文件格式是否正确",
                "检查修改内容是否合理",
                "尝试使用 --dry-run 预览修改"
            ]
        },
        ErrorType.PATH_CONFLICT: {
            "description": "路径冲突",
            "suggestions": [
                "检查新路径是否已存在",
                "确认新路径不会与其他路径产生冲突",
                "考虑使用不同的路径名称"
            ]
        },
        ErrorType.UNKNOWN_SOURCE: {
            "description": "未知的源类型",
            "suggestions": [
                "确认源类型是否为 menu.d、controller 或 ucode",
                "检查配置文件中的 source 字段"
            ]
        },
        ErrorType.FILE_VALIDATION_ERROR: {
            "description": "文件验证失败",
            "suggestions": [
                "检查文件是否存在",
                "确认文件是否可读",
                "检查文件大小是否合理"
            ]
        }
    }

    def __init__(self):
        """初始化错误处理器"""
        pass

    def get_error_info(self, error_type: ErrorType, context: Optional[Dict] = None) -> Dict:
        """获取错误信息

        Args:
            error_type: 错误类型
            context: 上下文信息

        Returns:
            包含错误描述和建议的字典
        """
        error_info = self.ERROR_MESSAGES.get(error_type, {
            "description": "未知错误",
            "suggestions": ["联系技术支持"]
        })

        result = {
            "type": error_type.value,
            "description": error_info["description"],
            "suggestions": error_info["suggestions"].copy(),
            "context": context or {}
        }

        return result

    def format_error_message(self, error_type: ErrorType, 
                           error_message: str,
                           context: Optional[Dict] = None) -> str:
        """格式化错误消息

        Args:
            error_type: 错误类型
            error_message: 错误消息
            context: 上下文信息

        Returns:
            格式化后的错误消息
        """
        error_info = self.get_error_info(error_type, context)

        lines = [
            f"错误类型: {error_info['description']} ({error_info['type']})",
            f"错误消息: {error_message}",
            "",
            "修复建议:"
        ]

        for i, suggestion in enumerate(error_info['suggestions'], 1):
            lines.append(f"  {i}. {suggestion}")

        if context:
            lines.append("")
            lines.append("上下文信息:")
            for key, value in context.items():
                lines.append(f"  {key}: {value}")

        return "\n".join(lines)

    def format_validation_errors(self, errors: List[str], warnings: List[str] = None) -> str:
        """格式化验证错误

        Args:
            errors: 错误列表
            warnings: 警告列表

        Returns:
            格式化后的验证错误消息
        """
        lines = []

        if errors:
            lines.append("验证错误:")
            for i, error in enumerate(errors, 1):
                lines.append(f"  {i}. {error}")
            lines.append("")

        if warnings:
            lines.append("验证警告:")
            for i, warning in enumerate(warnings, 1):
                lines.append(f"  {i}. {warning}")

        return "\n".join(lines)

    def get_suggestion_for_error(self, error_type: ErrorType, error_detail: str) -> Optional[str]:
        """根据错误详情获取特定建议

        Args:
            error_type: 错误类型
            error_detail: 错误详情

        Returns:
            修复建议
        """
        error_info = self.ERROR_MESSAGES.get(error_type)
        if not error_info:
            return None

        # 根据错误详情提供特定建议
        if error_type == ErrorType.VALIDATION_ERROR:
            if "路径" in error_detail and "已存在" in error_detail:
                return "路径冲突：请选择一个不同的路径名称，或先删除冲突的路径"
            elif "路径" in error_detail and "不以 'admin/' 开头" in error_detail:
                return "路径格式：建议使用 'admin/' 作为路径前缀"
            elif "标题" in error_detail and "不能为空" in error_detail:
                return "标题为空：请提供一个有效的标题"
            elif "排序值" in error_detail and "必须是整数" in error_detail:
                return "排序值错误：请提供一个整数值"
            elif "排序值" in error_detail and "负数" in error_detail:
                return "排序值为负：虽然可以使用负数，但建议使用正数"
            elif "别名" in error_detail and "格式无效" in error_detail:
                return "别名格式错误：请检查别名格式，确保不包含特殊字符"

        elif error_type == ErrorType.FILE_VALIDATION_ERROR:
            if "文件不存在" in error_detail:
                return "文件不存在：请确认文件路径正确"
            elif "文件为空" in error_detail:
                return "文件为空：请检查文件内容"
            elif "文件过大" in error_detail:
                return "文件过大：建议将大文件拆分为多个小文件"

        # 返回通用建议
        return error_info["suggestions"][0] if error_info["suggestions"] else None


# 全局错误处理器实例
_global_error_handler: Optional[ErrorHandler] = None


def get_error_handler() -> ErrorHandler:
    """获取全局错误处理器实例

    Returns:
        ErrorHandler 实例
    """
    global _global_error_handler
    if _global_error_handler is None:
        _global_error_handler = ErrorHandler()
    return _global_error_handler
