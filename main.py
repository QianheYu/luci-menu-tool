#!/usr/bin/env python3
"""
LuCI Menu Path and Priority Tool
Entry point: python3 LuciMenuTool/main.py or python3 -m LuciMenuTool.main

Usage:
    python3 LuciMenuTool/main.py --scan <feed_path>
    python3 LuciMenuTool/main.py --scan <feed_path> --export -o output.json
    python3 LuciMenuTool/main.py --scan <feed_path> --apply -i override.json
    python3 LuciMenuTool/main.py --scan <feed_path> --apply -i override.json --dry-run
    python3 LuciMenuTool/main.py --restore <file_path>
    python3 LuciMenuTool/main.py --restore-all
    python3 LuciMenuTool/main.py --list-backups
    python3 LuciMenuTool/main.py --clean-backups <days>
"""

import argparse
import json
import sys
import os
from pathlib import Path
from typing import Dict, List

# Ensure the parent directory is in the path so LuciMenuTool can be imported
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from LuciMenuTool.core.registry import registry
from LuciMenuTool.core.models import Change, MenuEntry
from LuciMenuTool.core.logger import get_logger
from LuciMenuTool.core.validator import Validator
from LuciMenuTool.core.error_handler import ErrorHandler, ErrorType
from LuciMenuTool.core.backup import BackupManager


def main():
    parser = argparse.ArgumentParser(
        description="LuCI Menu Path and Priority Tool for OpenWrt packages"
    )

    parser.add_argument(
        "--scan",
        type=str,
        help="Scan luci-app packages from specified feed path"
    )

    parser.add_argument(
        "--export",
        action="store_true",
        help="Export menu info to file (use with --scan and --output)"
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply override configuration from file (use with --scan and --input)"
    )

    parser.add_argument(
        "-i", "--input",
        type=str,
        help="Input file path (for --apply)"
    )

    parser.add_argument(
        "-o", "--output",
        type=str,
        help="Output file path (for --export)"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without applying (used with --apply)"
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Force apply changes even when path conflicts exist"
    )

    parser.add_argument(
        "--log-dir",
        type=str,
        help="Directory to store log files (default: no file logging)"
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output for detailed logging"
    )

    parser.add_argument(
        "--backup-dir",
        type=str,
        help="Directory to store backups (default: .lucimenutool/backups)"
    )

    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Disable automatic backup before applying changes"
    )

    parser.add_argument(
        "--restore",
        type=str,
        help="Restore file from backup (provide original file path)"
    )

    parser.add_argument(
        "--restore-all",
        action="store_true",
        help="Restore all files from backups"
    )

    parser.add_argument(
        "--list-backups",
        action="store_true",
        help="List all backups"
    )

    parser.add_argument(
        "--clean-backups",
        type=int,
        metavar="DAYS",
        help="Clean backups older than specified days"
    )

    args = parser.parse_args()

    # Initialize logger
    log_dir = Path(args.log_dir) if args.log_dir else None
    logger = get_logger(log_dir, args.verbose)

    # Initialize backup manager
    backup_dir = Path(args.backup_dir) if args.backup_dir else None
    backup_manager = BackupManager(backup_dir, logger)

    # Handle backup-related commands
    if args.list_backups:
        list_backups(backup_manager)
        return

    if args.restore:
        restore_backup(backup_manager, args.restore)
        return

    if args.restore_all:
        restore_all_backups(backup_manager)
        return

    if args.clean_backups:
        clean_backups(backup_manager, args.clean_backups)
        return

    if args.scan:
        packages = scan_feed(args.scan, logger)

        if args.export and args.output:
            export_packages(packages, args.output, logger)
        elif args.apply and args.input:
            apply_override(args.scan, args.input, dry_run=args.dry_run, logger=logger,
                         backup_manager=backup_manager, no_backup=args.no_backup, force=args.force)
        else:
            for pkg_name, info in packages.items():
                trees_summary = []
                for tree in info.get("menu_trees", []):
                    children_count = len(tree.get("children", []))
                    trees_summary.append(f"{tree['root_path']} (+{children_count} children)")
                trees_str = "; ".join(trees_summary) if trees_summary else "(no menu)"
                print(f"{pkg_name}: {trees_str} (source: {info['source']})")
    else:
        parser.print_help()


def scan_feed(feed_path: str, logger) -> Dict[str, Dict]:
    """Scan luci feed and extract menu info."""
    import glob
    feed_dir = Path(feed_path)
    if not feed_dir.exists():
        logger.log_error("FILE_NOT_FOUND", f"Feed path '{feed_path}' does not exist.")
        sys.exit(1)

    logger.info(f"开始扫描 feed 目录: {feed_path}")
    packages = {}
    app_dirs = glob.glob(str(feed_dir / "luci-app-*"))
    app_dirs.extend(glob.glob(str(feed_dir / "**" / "luci-app-*"), recursive=True))

    seen = set()
    unique_app_dirs = []
    for app_dir in app_dirs:
        if app_dir not in seen and Path(app_dir).is_dir():
            seen.add(app_dir)
            unique_app_dirs.append(app_dir)

    logger.info(f"找到 {len(unique_app_dirs)} 个 luci-app 包")

    for app_dir in unique_app_dirs:
        pkg_path = Path(app_dir)
        pkg_name = pkg_path.name
        logger.debug(f"处理包: {pkg_name}")
        pkg_info = _process_package(pkg_path, logger)
        if pkg_info:
            packages[pkg_name] = pkg_info
            logger.debug(f"成功处理包: {pkg_name} (source: {pkg_info['source']})")

    logger.info(f"扫描完成，共处理 {len(packages)} 个包")
    return packages


def _process_package(pkg_path: Path, logger) -> Dict:
    """Process a single package directory."""
    info = {
        "name": pkg_path.name,
        "pkg_path": str(pkg_path),
        "source": "unknown",
        "file": "",
        "makefile": {},
        "menu_trees": []
    }

    menu_d_paths = [
        pkg_path / "root" / "usr" / "share" / "luci" / "menu.d",
        pkg_path / "luasrc" / "luci" / "menu.d",
        pkg_path / "menu.d"
    ]

    for menu_d_path in menu_d_paths:
        if menu_d_path.exists() and list(menu_d_path.glob("*.json")):
            parser = registry.get_parser("menu.d")
            json_files = list(menu_d_path.glob("*.json"))
            if json_files:
                entries = []
                for jf in json_files:
                    logger.debug(f"  解析 menu.d 文件: {jf.relative_to(pkg_path)}")
                    entries.extend(parser.parse(jf))
                if entries:
                    info["source"] = "menu.d"
                    info["file"] = str(json_files[0].relative_to(pkg_path))
                    info["menu_trees"] = _build_menu_trees(entries)
                    return info

    controller_paths = [
        pkg_path / "luasrc" / "controller",
        pkg_path / "controller"
    ]
    for ctrl_path in controller_paths:
        if ctrl_path.exists():
            parser = registry.get_parser("controller")
            lua_files = list(ctrl_path.rglob("*.lua"))
            if lua_files:
                entries = []
                for lf in lua_files:
                    logger.debug(f"  解析 controller 文件: {lf.relative_to(pkg_path)}")
                    entries.extend(parser.parse(lf))
                if entries:
                    info["source"] = "controller"
                    info["file"] = str(lua_files[0].relative_to(pkg_path))
                    info["menu_trees"] = _build_menu_trees(entries)
                    return info

    ucode_paths = [pkg_path / "ucode" / "controller"]
    for ucode_path in ucode_paths:
        if ucode_path.exists():
            parser = registry.get_parser("ucode")
            ucode_files = list(ucode_path.rglob("*.uc"))
            if ucode_files:
                entries = []
                for uf in ucode_files:
                    logger.debug(f"  解析 ucode 文件: {uf.relative_to(pkg_path)}")
                    entries.extend(parser.parse(uf))
                if entries:
                    info["source"] = "ucode"
                    info["file"] = str(ucode_files[0].relative_to(pkg_path))
                    info["menu_trees"] = _build_menu_trees(entries)
                    return info

    return info


def _build_menu_trees(entries: List[MenuEntry]) -> List[Dict]:
    """Build menu tree structure from flat entries."""
    if not entries:
        return []

    # Collect all potential root paths (first 3 segments, or full path if < 3)
    all_root_candidates = set()
    for entry in entries:
        parts = entry.path.split("/")
        if len(parts) >= 3:
            all_root_candidates.add("/".join(parts[:3]))
        elif len(parts) == 2:
            all_root_candidates.add(entry.path)

    # Filter: a root should not be a child of another root
    true_roots = set()
    for candidate in all_root_candidates:
        is_child = False
        for other in all_root_candidates:
            if other != candidate and candidate.startswith(other + "/"):
                is_child = True
                break
        if not is_child:
            true_roots.add(candidate)

    menu_trees = []
    for root_path in sorted(true_roots):
        root_entry = next((e for e in entries if e.path == root_path), None)

        tree = {
            "root_path": root_path,
            "root_title": root_entry.title if root_entry else "",
            "root_order": root_entry.order if root_entry else "",
            "children": []
        }
        if root_entry and root_entry.alias:
            tree["root_alias"] = root_entry.alias

        for entry in entries:
            if entry.path != root_path and entry.path.startswith(root_path + "/"):
                child = {
                    "path": entry.path,
                    "title": entry.title,
                    "order": entry.order
                }
                if entry.alias:
                    child["alias"] = entry.alias
                tree["children"].append(child)

        menu_trees.append(tree)

    return menu_trees


def export_packages(packages: Dict[str, Dict], output_path: str, logger):
    """Export packages to JSON file."""
    logger.info(f"开始导出到文件: {output_path}")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(packages, f, ensure_ascii=False, indent=2)
    logger.info(f"成功导出 {len(packages)} 个包到 {output_path}")
    print(f"Exported {len(packages)} packages to {output_path}")


def apply_override(feed_path: str, input_path: str, dry_run: bool = False, 
                logger=None, backup_manager=None, no_backup=False, force=False):
    """Apply override configuration."""
    if logger is None:
        logger = get_logger()

    if not Path(input_path).exists():
        logger.log_error("FILE_NOT_FOUND", f"Input file '{input_path}' does not exist.")
        print(f"Error: Input file '{input_path}' does not exist.")
        sys.exit(1)

    logger.info(f"开始应用配置文件: {input_path}")
    logger.info(f"Feed 路径: {feed_path}")
    logger.info(f"Dry run 模式: {dry_run}")
    logger.info(f"备份功能: {'禁用' if no_backup else '启用'}")

    with open(input_path, 'r', encoding='utf-8') as f:
        overrides = json.load(f)

    feed_dir = Path(feed_path)
    applied = 0
    failed = 0

    # 初始化验证器和错误处理器
    validator = Validator(logger)
    error_handler = ErrorHandler()

    # 收集所有已存在的路径，用于检测冲突
    all_existing_paths = _collect_all_paths(feed_dir, overrides, logger)

    for pkg_name, override in overrides.items():
        pkg_dir = feed_dir / pkg_name
        if not pkg_dir.exists():
            logger.warning(f"包 '{pkg_name}' 不存在，跳过")
            print(f"Warning: Package '{pkg_name}' not found, skipping.")
            continue

        source = override.get("source", "")
        file_path = override.get("file", "")
        menu_trees = override.get("menu_trees", [])

        if not menu_trees:
            logger.debug(f"包 '{pkg_name}' 没有菜单树，跳过")
            continue

        changes = _extract_changes(menu_trees)
        if not changes:
            logger.debug(f"包 '{pkg_name}' 没有需要应用的修改，跳过")
            continue

        logger.info(f"处理包: {pkg_name} ({len(changes)} 个修改)")

        # 验证修改
        validation_result = validator.validate_changes(changes, all_existing_paths, force=force)
        if validation_result.errors:
            logger.log_error("VALIDATION_ERROR", 
                           f"包 '{pkg_name}' 验证失败",
                           f"错误: {', '.join(validation_result.errors)}")
            print(f"Error: Package '{pkg_name}' validation failed:")
            for error in validation_result.errors:
                print(f"  - {error}")
                # 提供修复建议
                suggestion = error_handler.get_suggestion_for_error(ErrorType.VALIDATION_ERROR, error)
                if suggestion:
                    print(f"    建议: {suggestion}")
            failed += 1
            continue

        if validation_result.warnings:
            logger.warning(f"包 '{pkg_name}' 验证警告: {', '.join(validation_result.warnings)}")
            print(f"Warning: Package '{pkg_name}' validation warnings:")
            for warning in validation_result.warnings:
                print(f"  - {warning}")

        if dry_run:
            print(f"[DRY RUN] Would update {pkg_name}:")
            for change in changes:
                print(f"  - {change.old_path}: ", end="")
                updates = []
                if change.new_path:
                    updates.append(f"path->{change.new_path}")
                    logger.log_change("PATH", change.old_path, change.new_path)
                if change.new_title is not None:
                    updates.append(f"title->{change.new_title}")
                    logger.log_change("TITLE", change.old_path, change.new_title)
                if change.new_order is not None:
                    updates.append(f"order->{change.new_order}")
                    logger.log_change("ORDER", change.old_path, str(change.new_order))
                if change.new_alias is not None:
                    updates.append(f"alias->{change.new_alias}")
                    logger.log_change("ALIAS", change.old_path, change.new_alias)
                print(", ".join(updates))
        else:
            source_file = pkg_dir / file_path
            if not source_file.exists():
                logger.log_error("FILE_NOT_FOUND", 
                               f"Source file '{source_file}' not found for {pkg_name}",
                               f"Package: {pkg_name}, File: {file_path}")
                print(f"Warning: Source file '{source_file}' not found for {pkg_name}.")
                failed += 1
                continue

            if source == "menu.d":
                applier = registry.get_applier("menu.d")
            elif source == "controller":
                applier = registry.get_applier("controller")
            elif source == "ucode":
                applier = registry.get_applier("ucode")
            else:
                logger.log_error("UNKNOWN_SOURCE", 
                               f"Unknown source type '{source}' for {pkg_name}",
                               f"Package: {pkg_name}")
                print(f"Warning: Unknown source type '{source}' for {pkg_name}.")
                failed += 1
                continue

            # 验证文件
            file_validation = validator.validate_file_before_apply(source_file, changes)
            if file_validation.errors:
                logger.log_error("FILE_VALIDATION_ERROR",
                               f"文件验证失败: {source_file}",
                               f"错误: {', '.join(file_validation.errors)}")
                print(f"Error: File validation failed for {source_file}:")
                for error in file_validation.errors:
                    print(f"  - {error}")
                    # 提供修复建议
                    suggestion = error_handler.get_suggestion_for_error(ErrorType.FILE_VALIDATION_ERROR, error)
                    if suggestion:
                        print(f"    建议: {suggestion}")
                failed += 1
                continue

            if file_validation.warnings:
                logger.warning(f"文件验证警告: {source_file} - {', '.join(file_validation.warnings)}")
                print(f"Warning: File validation warnings for {source_file}:")
                for warning in file_validation.warnings:
                    print(f"  - {warning}")

            # 创建备份
            if not no_backup and not dry_run and backup_manager:
                backup_path = backup_manager.create_backup(source_file)
                if backup_path:
                    logger.info(f"已创建备份: {backup_path}")
                else:
                    logger.warning(f"备份创建失败，继续应用修改")

            logger.log_file_start(source_file)
            try:
                applier.apply(source_file, changes)
                logger.log_file_end(source_file, True, len(changes))
                print(f"Updated {pkg_name}")
                applied += 1
            except Exception as e:
                logger.log_error("APPLY_ERROR", 
                               f"Error updating {pkg_name}: {e}",
                               f"File: {source_file}, Changes: {len(changes)}")
                logger.log_file_end(source_file, False, len(changes))
                print(f"Error updating {pkg_name}: {e}")
                failed += 1

    logger.info(f"应用完成: 成功 {applied} 个，失败 {failed} 个")
    print(f"Applied {applied} overrides")
    if failed > 0:
        print(f"Failed: {failed} packages")


def _collect_all_paths(feed_dir: Path, overrides: Dict, logger) -> Dict[str, str]:
    """收集所有已存在的路径，用于检测冲突

    Args:
        feed_dir: feed 目录
        overrides: 覆盖配置
        logger: 日志记录器

    Returns:
        路径到包名的映射字典
    """
    all_paths = {}

    for pkg_name, override in overrides.items():
        pkg_dir = feed_dir / pkg_name
        if not pkg_dir.exists():
            continue

        menu_trees = override.get("menu_trees", [])
        for tree in menu_trees:
            root_path = tree.get("root_path", "")
            if root_path:
                all_paths[root_path] = pkg_name

            for child in tree.get("children", []):
                child_path = child.get("path", "")
                if child_path:
                    all_paths[child_path] = pkg_name

    logger.debug(f"收集到 {len(all_paths)} 个已存在的路径")
    return all_paths


def _extract_changes(menu_trees: List[Dict]) -> List[Change]:
    """Extract changes from menu_trees.

    Only creates a Change when an explicit modification field is present:
    - root_new_path / new_path: path rename
    - root_new_title / new_title: title change
    - root_new_order / new_order: order change
    - root_new_alias / new_alias: alias change
    """
    changes = []
    for tree in menu_trees:
        root_path = tree.get("root_path", "")
        root_new_path = tree.get("root_new_path")
        root_new_title = tree.get("root_new_title")
        root_new_order = tree.get("root_new_order")
        root_new_alias = tree.get("root_new_alias")

        if root_new_path or root_new_title is not None or root_new_order is not None or root_new_alias is not None:
            changes.append(Change(
                old_path=root_path,
                new_path=root_new_path,
                new_title=root_new_title,
                new_order=root_new_order,
                new_alias=root_new_alias
            ))

        for child in tree.get("children", []):
            path = child.get("path", "")
            new_path = child.get("new_path")
            new_title = child.get("new_title")
            new_order = child.get("new_order")
            new_alias = child.get("new_alias")

            if new_path or new_title is not None or new_order is not None or new_alias is not None:
                changes.append(Change(
                    old_path=path,
                    new_path=new_path,
                    new_title=new_title,
                    new_order=new_order,
                    new_alias=new_alias
                ))

    return changes


def list_backups(backup_manager: BackupManager):
    """列出所有备份

    Args:
        backup_manager: 备份管理器
    """
    backups = backup_manager.list_backups()

    if not backups:
        print("没有找到任何备份")
        return

    print(f"\n备份列表 (共 {len(backups)} 个):")
    print("=" * 80)

    for backup in backups:
        status = "✓" if backup["exists"] else "✗"
        print(f"{status} 原始路径: {backup['original_path']}")
        print(f"  备份路径: {backup['backup_path']}")
        print(f"  备份时间: {backup['timestamp']}")
        print(f"  文件大小: {backup['size']} 字节")
        print("-" * 80)

    backup_dir = backup_manager.get_backup_dir()
    print(f"\n备份目录: {backup_dir}")


def restore_backup(backup_manager: BackupManager, file_path: str):
    """从备份恢复文件

    Args:
        backup_manager: 备份管理器
        file_path: 要恢复的文件路径
    """
    source_file = Path(file_path)

    if not source_file.exists():
        print(f"错误: 文件不存在: {file_path}")
        return

    print(f"正在恢复文件: {file_path}")

    if backup_manager.restore_backup(source_file):
        print(f"✓ 成功恢复文件: {file_path}")
    else:
        print(f"✗ 恢复文件失败: {file_path}")
        print("提示: 使用 --list-backups 查看可用备份")


def restore_all_backups(backup_manager: BackupManager):
    """恢复所有备份文件

    Args:
        backup_manager: 备份管理器
    """
    backups = backup_manager.list_backups()

    if not backups:
        print("没有找到任何备份文件")
        return

    print(f"找到 {len(backups)} 个备份文件")
    print("=" * 80)

    success_count = 0
    fail_count = 0

    for backup in backups:
        original_path = backup['original_path']
        exists = backup['exists']

        if not exists:
            print(f"✗ 跳过: {original_path} (备份文件不存在)")
            fail_count += 1
            continue

        print(f"正在恢复: {original_path}")

        if backup_manager.restore_backup(Path(original_path)):
            print(f"✓ 成功恢复: {original_path}")
            success_count += 1
        else:
            print(f"✗ 恢复失败: {original_path}")
            fail_count += 1
        print("-" * 80)

    print(f"\n恢复完成: 成功 {success_count} 个，失败 {fail_count} 个")


def clean_backups(backup_manager: BackupManager, days: int):
    """清理旧备份

    Args:
        backup_manager: 备份管理器
        days: 保留天数
    """
    if days <= 0:
        print("错误: 保留天数必须大于 0")
        return

    print(f"正在清理 {days} 天前的旧备份...")
    backup_manager.clean_old_backups(days)
    print(f"✓ 清理完成")

    # 显示剩余备份
    backups = backup_manager.list_backups()
    print(f"\n剩余备份: {len(backups)} 个")


if __name__ == "__main__":
    main()
