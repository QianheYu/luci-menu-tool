#!/usr/bin/env python3
"""
日志模块 - 记录详细的修改过程
"""

import logging
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime


class Logger:
    """日志记录器，用于记录详细的修改过程"""

    def __init__(self, log_dir: Optional[Path] = None, verbose: bool = False):
        """初始化日志记录器

        Args:
            log_dir: 日志目录，如果为None则不记录到文件
            verbose: 是否在控制台输出详细日志
        """
        self.logger = logging.getLogger('LuciMenuTool')
        self.logger.setLevel(logging.DEBUG)

        # 清除已有的处理器
        self.logger.handlers.clear()

        # 控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO if not verbose else logging.DEBUG)
        console_formatter = logging.Formatter('%(message)s')
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)

        # 文件处理器
        if log_dir:
            log_dir = Path(log_dir)
            log_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            log_file = log_dir / f'lucimenutool_{timestamp}.log'

            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)
            file_formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(file_formatter)
            self.logger.addHandler(file_handler)

            self.log_file = log_file
        else:
            self.log_file = None

    def info(self, message: str):
        """记录信息级别日志"""
        self.logger.info(message)

    def debug(self, message: str):
        """记录调试级别日志"""
        self.logger.debug(message)

    def warning(self, message: str):
        """记录警告级别日志"""
        self.logger.warning(message)

    def error(self, message: str):
        """记录错误级别日志"""
        self.logger.error(message)

    def log_separator(self, prefix: str = "", suffix: str = ""):
        """打印分隔符"""
        self.info(f"{prefix}{'='*60}{suffix}")

    def log_file_start(self, file_path: Path):
        """记录开始处理文件"""
        # self.info(f"\n{'='*60}")
        self.info(f"处理文件: {file_path}")
        self.debug(f"文件绝对路径: {file_path.absolute()}")

    def log_file_end(self, file_path: Path, success: bool, changes_count: int = 0):
        """记录文件处理结束"""
        status = "成功" if success else "失败"
        self.info(f"文件处理{status}: {file_path} (修改数量: {changes_count})")
        # self.info(f"{'='*60}\n")

    def log_change(self, change_type: str, old_value: str, new_value: str, details: str = ""):
        """记录修改详情"""
        self.debug(f"  [{change_type}] {old_value} -> {new_value}")
        if details:
            self.debug(f"    详情: {details}")

    def log_error(self, error_type: str, message: str, context: str = ""):
        """记录错误详情"""
        self.error(f"[{error_type}] {message}")
        if context:
            self.debug(f"  上下文: {context}")

    def get_log_file(self) -> Optional[Path]:
        """获取日志文件路径"""
        return self.log_file


# 全局日志实例
_global_logger: Optional[Logger] = None


def get_logger(log_dir: Optional[Path] = None, verbose: bool = False) -> Logger:
    """获取全局日志实例

    Args:
        log_dir: 日志目录
        verbose: 是否在控制台输出详细日志

    Returns:
        Logger实例
    """
    global _global_logger
    if _global_logger is None or log_dir is not None or verbose:
        _global_logger = Logger(log_dir, verbose)
    return _global_logger
