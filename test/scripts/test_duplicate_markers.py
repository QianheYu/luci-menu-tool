#!/usr/bin/env python3
"""
Test script to verify the duplicate markers cleanup functionality.
This script tests the _clean_duplicate_markers method in both LuaControllerApplier and MenuDApplier.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from LuciMenuTool.lua_controller.applier import LuaControllerApplier
from LuciMenuTool.menu_d.applier import MenuDApplier


def test_lua_applier():
    """Test LuaControllerApplier's _clean_duplicate_markers method."""
    print("Testing LuaControllerApplier...")
    applier = LuaControllerApplier()

    test_cases = [
        ("Title (Modified) (Modified)", "Title (Modified)"),
        ("标题 (已修改) (已修改)", "标题 (已修改)"),
        ("Title (Updated) (Updated)", "Title (Updated)"),
        ("标题 (已更新) (已更新)", "标题 (已更新)"),
        ("Title (Modified) (Updated)", "Title (Modified) (Updated)"),  # Different markers
        ("Title (Modified)", "Title (Modified)"),  # Single marker
        ("Title", "Title"),  # No marker
        ("Title (Modified) (Modified) (Modified)", "Title (Modified)"),  # Multiple duplicates
    ]

    passed = 0
    failed = 0

    for input_title, expected_output in test_cases:
        result = applier._clean_duplicate_markers(input_title)
        if result == expected_output:
            print(f"  ✓ '{input_title}' -> '{result}'")
            passed += 1
        else:
            print(f"  ✗ '{input_title}' -> '{result}' (expected: '{expected_output}')")
            failed += 1

    print(f"\nLuaControllerApplier: {passed} passed, {failed} failed\n")
    return failed == 0


def test_menu_d_applier():
    """Test MenuDApplier's _clean_duplicate_markers method."""
    print("Testing MenuDApplier...")
    applier = MenuDApplier()

    test_cases = [
        ("Title (Modified) (Modified)", "Title (Modified)"),
        ("标题 (已修改) (已修改)", "标题 (已修改)"),
        ("Title (Updated) (Updated)", "Title (Updated)"),
        ("标题 (已更新) (已更新)", "标题 (已更新)"),
        ("Title (Modified) (Updated)", "Title (Modified) (Updated)"),  # Different markers
        ("Title (Modified)", "Title (Modified)"),  # Single marker
        ("Title", "Title"),  # No marker
        ("Title (Modified) (Modified) (Modified)", "Title (Modified)"),  # Multiple duplicates
    ]

    passed = 0
    failed = 0

    for input_title, expected_output in test_cases:
        result = applier._clean_duplicate_markers(input_title)
        if result == expected_output:
            print(f"  ✓ '{input_title}' -> '{result}'")
            passed += 1
        else:
            print(f"  ✗ '{input_title}' -> '{result}' (expected: '{expected_output}')")
            failed += 1

    print(f"\nMenuDApplier: {passed} passed, {failed} failed\n")
    return failed == 0


if __name__ == "__main__":
    print("=" * 60)
    print("Testing Duplicate Markers Cleanup Functionality")
    print("=" * 60 + "\n")

    lua_ok = test_lua_applier()
    menu_d_ok = test_menu_d_applier()

    print("=" * 60)
    if lua_ok and menu_d_ok:
        print("All tests passed! ✓")
        sys.exit(0)
    else:
        print("Some tests failed! ✗")
        sys.exit(1)
