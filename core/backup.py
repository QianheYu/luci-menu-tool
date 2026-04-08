#!/usr/bin/env python3
"""
备份模块 - 在应用前自动备份源文件，支持一键恢复
"""

import shutil
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime
import json

from LuciMenuTool.core.logger import get_logger


class BackupManager:
    """备份管理器，用于管理文件的备份和恢复"""

    def __init__(self, backup_dir: Optional[Path] = None, logger=None):
        """初始化备份管理器

        Args:
            backup_dir: 备份目录，如果为None则使用默认目录
            logger: 日志记录器
        """
        self.logger = logger or get_logger()

        if backup_dir is None:
            # 默认备份目录
            backup_dir = Path.cwd() / ".lucimenutool" / "backups"

        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        # 备份元数据文件
        self.metadata_file = self.backup_dir / "backup_metadata.json"
        self.metadata = self._load_metadata()

    def _load_metadata(self) -> Dict:
        """加载备份元数据

        Returns:
            备份元数据字典
        """
        if not self.metadata_file.exists():
            return {}

        try:
            with open(self.metadata_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self.logger.warning(f"加载备份元数据失败: {e}")
            return {}

    def _save_metadata(self):
        """保存备份元数据"""
        try:
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(self.metadata, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"保存备份元数据失败: {e}")

    def create_backup(self, source_file: Path) -> Optional[Path]:
        """创建文件备份

        Args:
            source_file: 要备份的源文件

        Returns:
            备份文件路径，如果失败则返回None
        """
        if not source_file.exists():
            self.logger.warning(f"源文件不存在，无法备份: {source_file}")
            return None

        try:
            # 生成备份文件名
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            relative_path = source_file.relative_to(source_file.anchor)
            backup_name = f"{timestamp}_{relative_path.name}"
            backup_path = self.backup_dir / backup_name

            # 创建备份
            shutil.copy2(source_file, backup_path)

            # 记录元数据
            backup_key = str(source_file.absolute())
            self.metadata[backup_key] = {
                "backup_path": str(backup_path),
                "original_path": str(source_file.absolute()),
                "timestamp": timestamp,
                "size": source_file.stat().st_size
            }
            self._save_metadata()

            self.logger.info(f"创建备份: {source_file} -> {backup_path}")
            return backup_path

        except Exception as e:
            self.logger.error(f"创建备份失败: {source_file}, 错误: {e}")
            return None

    def restore_backup(self, source_file: Path) -> bool:
        """从备份恢复文件

        Args:
            source_file: 要恢复的源文件

        Returns:
            是否成功恢复
        """
        backup_key = str(source_file.absolute())

        if backup_key not in self.metadata:
            self.logger.warning(f"未找到备份: {source_file}")
            return False

        try:
            backup_info = self.metadata[backup_key]
            backup_path = Path(backup_info["backup_path"])

            if not backup_path.exists():
                self.logger.error(f"备份文件不存在: {backup_path}")
                return False

            # 恢复文件
            shutil.copy2(backup_path, source_file)

            self.logger.info(f"恢复备份: {backup_path} -> {source_file}")
            return True

        except Exception as e:
            self.logger.error(f"恢复备份失败: {source_file}, 错误: {e}")
            return False

    def list_backups(self) -> List[Dict]:
        """列出所有备份

        Returns:
            备份信息列表
        """
        backups = []

        for backup_key, backup_info in self.metadata.items():
            backup_path = Path(backup_info["backup_path"])
            if backup_path.exists():
                backups.append({
                    "original_path": backup_info["original_path"],
                    "backup_path": str(backup_path),
                    "timestamp": backup_info["timestamp"],
                    "size": backup_info["size"],
                    "exists": True
                })
            else:
                backups.append({
                    "original_path": backup_info["original_path"],
                    "backup_path": str(backup_path),
                    "timestamp": backup_info["timestamp"],
                    "size": backup_info["size"],
                    "exists": False
                })

        return backups

    def clean_old_backups(self, keep_days: int = 7):
        """清理旧备份

        Args:
            keep_days: 保留天数
        """
        import os
        from datetime import timedelta

        cutoff_time = datetime.now() - timedelta(days=keep_days)
        cleaned = 0

        for backup_key, backup_info in list(self.metadata.items()):
            backup_path = Path(backup_info["backup_path"])

            if not backup_path.exists():
                del self.metadata[backup_key]
                continue

            # 检查备份时间
            try:
                backup_time = datetime.strptime(backup_info["timestamp"], '%Y%m%d_%H%M%S')
                if backup_time < cutoff_time:
                    backup_path.unlink()
                    del self.metadata[backup_key]
                    cleaned += 1
                    self.logger.info(f"清理旧备份: {backup_path}")
            except Exception as e:
                self.logger.warning(f"检查备份时间失败: {backup_path}, 错误: {e}")

        if cleaned > 0:
            self._save_metadata()
            self.logger.info(f"清理了 {cleaned} 个旧备份")

    def get_backup_dir(self) -> Path:
        """获取备份目录

        Returns:
            备份目录路径
        """
        return self.backup_dir
