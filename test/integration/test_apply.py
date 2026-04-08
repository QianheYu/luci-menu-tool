#!/usr/bin/env python3
"""
Automated apply test for LuciMenuTool.

Steps:
1. Export current state to JSON
2. Back up all luci app files
3. Make random modifications to the JSON
4. Apply modifications
5. Verify each modification was correctly applied
6. Restore original files
7. Report results
"""

import json
import random
import sys
import os
import glob
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from LuciMenuTool.main import scan_feed, export_packages, apply_override

FEED_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "test_lede", "feeds", "luci", "applications")
EXPORT_FILE = "/tmp/test_apply_export.json"
MODIFIED_FILE = "/tmp/test_apply_modified.json"
BACKUP_DIR = "/tmp/test_apply_backup"


def backup_files():
    """Back up all luci app files."""
    if os.path.exists(BACKUP_DIR):
        shutil.rmtree(BACKUP_DIR)
    os.makedirs(BACKUP_DIR, exist_ok=True)

    app_dirs = glob.glob(os.path.join(FEED_PATH, "luci-app-*"))
    app_dirs.extend(glob.glob(os.path.join(FEED_PATH, "**", "luci-app-*"), recursive=True))

    for app_dir in app_dirs:
        if not os.path.isdir(app_dir):
            continue
        rel_path = os.path.relpath(app_dir, FEED_PATH)
        dest = os.path.join(BACKUP_DIR, rel_path)
        shutil.copytree(app_dir, dest, dirs_exist_ok=True)


def restore_files():
    """Restore luci app files from backup."""
    if not os.path.exists(BACKUP_DIR):
        return

    for item in os.listdir(BACKUP_DIR):
        src = os.path.join(BACKUP_DIR, item)
        dst = os.path.join(FEED_PATH, item)
        if os.path.isdir(src):
            if os.path.exists(dst):
                shutil.rmtree(dst)
            shutil.copytree(src, dst)


def modify_export(data):
    """Randomly modify the export data and track expected changes."""
    random.seed(42)  # For reproducible tests
    expected_changes = {}

    for pkg_name, pkg_info in list(data.items()):
        if random.random() > 0.3:
            continue

        menu_trees = pkg_info.get("menu_trees", [])
        if not menu_trees:
            continue

        source = pkg_info.get("source", "")
        file_path = pkg_info.get("file", "")

        pkg_changes = {
            "source": source,
            "file": file_path,
            "modifications": []
        }

        for tree in menu_trees:
            root_path = tree.get("root_path", "")
            if not root_path:
                continue

            # Only modify root if it has an actual order in the source
            root_order = tree.get("root_order", "")
            root_title = tree.get("root_title", "")

            # Randomly choose what to modify
            mod_options = ["skip"]
            if root_order:
                mod_options.append("order")
            if root_title:
                mod_options.append("title")

            # Also try modifying children
            children = tree.get("children", [])
            if children:
                mod_options.append("child_order")

            mod_type = random.choice(mod_options)

            if mod_type == "order" and root_order:
                new_order = random.randint(1, 999)
                tree["root_new_order"] = str(new_order)  # Add new_* field
                pkg_changes["modifications"].append({
                    "path": root_path,
                    "type": "order",
                    "old": root_order,
                    "new": str(new_order)
                })

            elif mod_type == "title" and root_title:
                new_title = root_title + "_MOD"
                tree["root_new_title"] = new_title  # Add new_* field
                pkg_changes["modifications"].append({
                    "path": root_path,
                    "type": "title",
                    "old": root_title,
                    "new": new_title
                })

            elif mod_type == "child_order" and children:
                child = random.choice(children)
                child_path = child.get("path", "")
                child_order = child.get("order", "")
                if child_path and child_order:
                    new_order = random.randint(1, 999)
                    child["new_order"] = str(new_order)  # Add new_* field
                    pkg_changes["modifications"].append({
                        "path": child_path,
                        "type": "order",
                        "old": child_order,
                        "new": str(new_order)
                    })

        if pkg_changes["modifications"]:
            expected_changes[pkg_name] = pkg_changes

    return expected_changes


def verify_menu_d_change(pkg_name, file_path, modifications):
    """Verify menu.d JSON changes."""
    full_path = os.path.join(FEED_PATH, pkg_name, file_path)
    if not os.path.exists(full_path):
        return False, f"File not found: {full_path}"

    with open(full_path) as f:
        data = json.load(f)

    for mod in modifications:
        path = mod["path"]
        mod_type = mod["type"]

        if mod_type == "order":
            new_order_str = mod["new"]  # Keep as string for comparison
            if path in data:
                actual = data[path].get("order")
                # Compare string representations to handle "107" vs 107
                if str(actual) != str(new_order_str):
                    return False, f"Order mismatch for {path}: expected {new_order_str}, got {actual}"

        elif mod_type == "title":
            if path in data:
                actual = data[path].get("title")
                if actual != mod["new"]:
                    return False, f"Title mismatch for {path}: expected {mod['new']!r}, got {actual!r}"

    return True, "OK"


def verify_lua_change(pkg_name, file_path, modifications):
    """Verify Lua controller changes."""
    full_path = os.path.join(FEED_PATH, pkg_name, file_path)
    if not os.path.exists(full_path):
        return False, f"File not found: {full_path}"

    with open(full_path) as f:
        content = f.read()

    for mod in modifications:
        mod_type = mod["type"]

        if mod_type == "order":
            new_order = mod["new"]
            # Check if order appears as a number (without quotes)
            if new_order not in content:
                # Also check for order followed by comma or ')'
                import re
                # Pattern: number possibly negative, followed by comma, space, or ')'
                pattern = r'\b' + re.escape(new_order) + r'\b'
                if not re.search(pattern, content):
                    lines = content.split('\n')
                    for i, line in enumerate(lines):
                        if 'entry' in line or 'node' in line:
                            if i < len(lines) - 1:
                                context = '\n'.join(lines[max(0,i-2):min(len(lines),i+3)])
                                break
                    return False, f"Order {new_order} not found in {full_path}. Context: {context[:200]}"

        elif mod_type == "title":
            new_title = mod["new"]
            if new_title not in content:
                # Check if title appears inside _("...")
                import re
                # Look for _("...") pattern
                matches = re.findall(r'_\(\s*"([^"]+)"\s*\)', content)
                found = any(new_title in m for m in matches)
                if not found:
                    # Also check for plain "title"
                    matches = re.findall(r'"([^"]+)"', content)
                    found = any(new_title in m for m in matches)
                if not found:
                    return False, f"Title {new_title!r} not found in {full_path}"

    return True, "OK"


def main():
    print("=" * 60)
    print("LuciMenuTool Apply Test")
    print("=" * 60)

    # Step 1: Back up files
    print("\n[Step 1] Backing up files...")
    backup_files()
    print("  Done")

    # Step 2: Export current state
    print("\n[Step 2] Exporting current state...")
    packages = scan_feed(FEED_PATH)
    export_packages(packages, EXPORT_FILE)
    print(f"  Exported {len(packages)} packages")

    # Step 3: Modify export
    print("\n[Step 3] Modifying export...")
    with open(EXPORT_FILE) as f:
        data = json.load(f)

    expected_changes = modify_export(data)
    print(f"  Modified {len(expected_changes)} packages")

    with open(MODIFIED_FILE, 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # Step 4: Apply modifications
    print("\n[Step 4] Applying modifications...")
    apply_override(FEED_PATH, MODIFIED_FILE)

    # Step 5: Verify each change
    print("\n[Step 5] Verifying changes...")
    passed = 0
    failed = 0
    errors = []

    for pkg_name, changes in expected_changes.items():
        source = changes["source"]
        file_path = changes["file"]
        modifications = changes["modifications"]

        if source == "menu.d":
            ok, msg = verify_menu_d_change(pkg_name, file_path, modifications)
        elif source == "controller":
            ok, msg = verify_lua_change(pkg_name, file_path, modifications)
        else:
            ok, msg = True, "Skipped (unknown source)"

        if ok:
            passed += 1
            print(f"  ✓ {pkg_name}: {msg}")
        else:
            failed += 1
            errors.append(f"{pkg_name}: {msg}")
            print(f"  ✗ {pkg_name}: {msg}")

    # Step 6: Restore files
    print("\n[Step 6] Restoring files...")
    restore_files()
    print("  Done")

    # Summary
    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    if errors:
        print("\nErrors:")
        for e in errors:
            print(f"  - {e}")
    print("=" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
