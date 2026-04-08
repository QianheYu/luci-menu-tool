
"""
测试 Lua Controller 中变量引用路径的情况
"""
import sys
import os
from pathlib import Path

# 确保父目录在路径中，以便导入LuciMenuTool
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from LuciMenuTool.core.models import Change
from LuciMenuTool.lua_controller.applier import LuaControllerApplier

def test_variable_reference():
    """测试使用变量引用路径的 entry"""
    print("="*60)
    print("测试: 变量引用路径")
    print("="*60)

    # 创建一个测试文件，包含变量引用路径的 entry
    test_lua_code = """
module("luci.controller.test", package.seeall)

function index()
    local admin_path = "admin"
    local system_path = "system"

    entry({admin_path, system_path, "test"}, cbi("test"), _("Test"), 50)
    entry({"admin", "network", "test2"}, cbi("test2"), _("Test2"), 60)
end
"""

    print("\n测试代码:")
    print(test_lua_code)

    # 解析并检查变量提取
    applier = LuaControllerApplier()

    try:
        from luaparser import ast
        tree = ast.parse(test_lua_code)
        variables = applier._extract_variables(tree)

        print("\n提取到的变量:")
        for var_name, var_value in variables.items():
            print(f"  {var_name} = \"{var_value}\"")

        # 查找所有 entry
        entry_count = 0
        entry_paths = []
        for node in ast.walk(tree):
            if hasattr(node, 'func') and hasattr(node.func, 'id') and node.func.id == "entry":
                entry_count += 1
                # 提取路径
                if node.args and isinstance(node.args[0], ast.Table):
                    parts = []
                    for field in node.args[0].fields:
                        val = field.value if isinstance(field, ast.Field) else field
                        if isinstance(val, ast.String):
                            s = val.s
                            if isinstance(s, bytes):
                                s = s.decode("utf-8", errors="ignore")
                            parts.append(s)
                        elif isinstance(val, ast.Name) and val.id in variables:
                            parts.append(variables[val.id])
                        else:
                            # 无法解析的变量或表达式
                            parts.append(f"<{val.id if isinstance(val, ast.Name) else 'unknown'}>")
                    if parts:
                        entry_paths.append("/".join(parts))

        print(f"\n找到 {entry_count} 个 entry:")
        for i, path in enumerate(entry_paths, 1):
            print(f"  {i}. {path}")

        # 检查是否能正确解析变量引用
        expected_paths = ["admin/system/test", "admin/network/test2"]

        # 第一个 entry 应该能正确解析变量引用
        if entry_paths[0] == expected_paths[0]:
            print("\n✅ 变量引用路径能正确解析")
            print(f"  期望: {expected_paths[0]}")
            print(f"  实际: {entry_paths[0]}")
            return True
        else:
            print("\n❌ 变量引用路径未能正确解析")
            print(f"  期望: {expected_paths[0]}")
            print(f"  实际: {entry_paths[0]}")
            return False

    except Exception as e:
        print(f"\n❌ 解析失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_complex_variable_reference():
    """测试更复杂的变量引用情况"""
    print("\n" + "="*60)
    print("测试: 复杂变量引用")
    print("="*60)

    # 创建一个测试文件，包含更复杂的变量引用
    test_lua_code = """
module("luci.controller.test", package.seeall)

function index()
    local base_path = "admin"
    local category = "system"
    local subcategory = "test"

    -- 使用多个变量
    entry({base_path, category, subcategory}, cbi("test"), _("Test"), 50)

    -- 混合使用变量和字符串
    entry({base_path, "network", "test2"}, cbi("test2"), _("Test2"), 60)

    -- 使用未定义的变量（应该跳过）
    entry({undefined_var, "test3"}, cbi("test3"), _("Test3"), 70)
end
"""

    print("\n测试代码:")
    print(test_lua_code)

    # 解析并检查变量提取
    applier = LuaControllerApplier()

    try:
        from luaparser import ast
        tree = ast.parse(test_lua_code)
        variables = applier._extract_variables(tree)

        print("\n提取到的变量:")
        for var_name, var_value in variables.items():
            print(f"  {var_name} = \"{var_value}\"")

        # 查找所有 entry
        entry_count = 0
        entry_paths = []
        for node in ast.walk(tree):
            if hasattr(node, 'func') and hasattr(node.func, 'id') and node.func.id == "entry":
                entry_count += 1
                # 提取路径
                if node.args and isinstance(node.args[0], ast.Table):
                    parts = []
                    resolvable = True
                    for field in node.args[0].fields:
                        val = field.value if isinstance(field, ast.Field) else field
                        if isinstance(val, ast.String):
                            s = val.s
                            if isinstance(s, bytes):
                                s = s.decode("utf-8", errors="ignore")
                            parts.append(s)
                        elif isinstance(val, ast.Name) and val.id in variables:
                            parts.append(variables[val.id])
                        else:
                            # 无法解析的变量或表达式
                            resolvable = False
                            break
                    if resolvable and parts:
                        entry_paths.append("/".join(parts))
                    else:
                        entry_paths.append("<unresolvable>")

        print(f"\n找到 {entry_count} 个 entry:")
        for i, path in enumerate(entry_paths, 1):
            print(f"  {i}. {path}")

        # 检查结果
        expected_results = [
            "admin/system/test",  # 全部使用变量
            "admin/network/test2",  # 混合使用变量和字符串
            "<unresolvable>"  # 使用未定义变量
        ]

        all_correct = True
        for i, (actual, expected) in enumerate(zip(entry_paths, expected_results), 1):
            if actual == expected:
                print(f"\n✅ Entry {i} 解析正确")
                print(f"  期望: {expected}")
                print(f"  实际: {actual}")
            else:
                print(f"\n❌ Entry {i} 解析不正确")
                print(f"  期望: {expected}")
                print(f"  实际: {actual}")
                all_correct = False

        return all_correct

    except Exception as e:
        print(f"\n❌ 解析失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("Lua Controller 变量引用测试")
    print("="*60)

    results = []

    # 测试 1: 基本变量引用
    results.append(("基本变量引用", test_variable_reference()))

    # 测试 2: 复杂变量引用
    results.append(("复杂变量引用", test_complex_variable_reference()))

    # 输出总结
    print("\n" + "="*60)
    print("测试总结")
    print("="*60)

    for test_name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{status} - {test_name}")

    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    print(f"\n通过: {passed_count}/{total_count}")

    if passed_count == total_count:
        print("\n✅ 所有测试通过，变量引用处理正常")
        return True
    else:
        print("\n❌ 部分测试失败，需要修复")
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
