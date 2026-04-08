#!/usr/bin/env python3
"""
LuCI Menu Path and Priority Tool
Entry point: python3 LuciMenuTool/main.py or python3 -m LuciMenuTool.main

Usage:
    python3 LuciMenuTool/main.py --scan <feed_path>
    python3 LuciMenuTool/main.py --scan <feed_path> --export -o output.json
    python3 LuciMenuTool/main.py --scan <feed_path> --apply -i override.json
    python3 LuciMenuTool/main.py --scan <feed_path> --apply -i override.json --dry-run
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
    
    args = parser.parse_args()
    
    if args.scan:
        packages = scan_feed(args.scan)
        
        if args.export and args.output:
            export_packages(packages, args.output)
        elif args.apply and args.input:
            apply_override(args.scan, args.input, dry_run=args.dry_run)
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


def scan_feed(feed_path: str) -> Dict[str, Dict]:
    """Scan luci feed and extract menu info."""
    import glob
    feed_dir = Path(feed_path)
    if not feed_dir.exists():
        print(f"Error: Feed path '{feed_path}' does not exist.")
        sys.exit(1)

    packages = {}
    app_dirs = glob.glob(str(feed_dir / "luci-app-*"))
    app_dirs.extend(glob.glob(str(feed_dir / "**" / "luci-app-*"), recursive=True))
    
    seen = set()
    unique_app_dirs = []
    for app_dir in app_dirs:
        if app_dir not in seen and Path(app_dir).is_dir():
            seen.add(app_dir)
            unique_app_dirs.append(app_dir)

    for app_dir in unique_app_dirs:
        pkg_path = Path(app_dir)
        pkg_name = pkg_path.name
        pkg_info = _process_package(pkg_path)
        if pkg_info:
            packages[pkg_name] = pkg_info

    return packages


def _process_package(pkg_path: Path) -> Dict:
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


def export_packages(packages: Dict[str, Dict], output_path: str):
    """Export packages to JSON file."""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(packages, f, ensure_ascii=False, indent=2)
    print(f"Exported {len(packages)} packages to {output_path}")


def apply_override(feed_path: str, input_path: str, dry_run: bool = False):
    """Apply override configuration."""
    if not Path(input_path).exists():
        print(f"Error: Input file '{input_path}' does not exist.")
        sys.exit(1)

    with open(input_path, 'r', encoding='utf-8') as f:
        overrides = json.load(f)

    feed_dir = Path(feed_path)
    applied = 0

    for pkg_name, override in overrides.items():
        pkg_dir = feed_dir / pkg_name
        if not pkg_dir.exists():
            print(f"Warning: Package '{pkg_name}' not found, skipping.")
            continue

        source = override.get("source", "")
        file_path = override.get("file", "")
        menu_trees = override.get("menu_trees", [])

        if not menu_trees:
            continue

        changes = _extract_changes(menu_trees)
        if not changes:
            continue
            
        if dry_run:
            print(f"[DRY RUN] Would update {pkg_name}:")
            for change in changes:
                print(f"  - {change.old_path}: ", end="")
                updates = []
                if change.new_path:
                    updates.append(f"path->{change.new_path}")
                if change.new_title is not None:
                    updates.append(f"title->{change.new_title}")
                if change.new_order is not None:
                    updates.append(f"order->{change.new_order}")
                if change.new_alias is not None:
                    updates.append(f"alias->{change.new_alias}")
                print(", ".join(updates))
        else:

            source_file = pkg_dir / file_path
            if not source_file.exists():
                print(f"Warning: Source file '{source_file}' not found for {pkg_name}.")
                continue

            if source == "menu.d":
                applier = registry.get_applier("menu.d")
            elif source == "controller":
                applier = registry.get_applier("controller")
            elif source == "ucode":
                applier = registry.get_applier("ucode")
            else:
                print(f"Warning: Unknown source type '{source}' for {pkg_name}.")
                continue

            try:
                applier.apply(source_file, changes)
                print(f"Updated {pkg_name}")
                applied += 1
            except Exception as e:
                print(f"Error updating {pkg_name}: {e}")

    print(f"Applied {applied} overrides")


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


if __name__ == "__main__":
    main()
