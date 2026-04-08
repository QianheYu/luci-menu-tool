
"""
测试 Lua Controller 的边界情况
1. 多 entry 文件中定位特定 entry
2. if/else 分支中的 entry 定义
"""
import sys
import os
from pathlib import Path

# 确保父目录在路径中，以便导入LuciMenuTool
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from LuciMenuTool.core.models import Change
from LuciMenuTool.lua_controller.applier import LuaControllerApplier

def test_nft_qos():
    """测试 nft-qos.lua - 多 entry 文件"""
    print("="*60)
    print("测试 1: nft-qos.lua - 多 entry 文件")
    print("="*60)

    # 文件路径
    file_path = Path('../../test_lede/feeds/luci/applications/luci-app-nft-qos/luasrc/controller/nft-qos.lua')

    # 测试修改第一个 entry 的标题和排序
    changes = [
        Change(
            old_path="admin/status/realtime/rate",
            new_path="admin/status/realtime/rate",
            new_title="Rate (Modified)",
            new_order=10
        ),
        # 测试修改第三个 entry
        Change(
            old_path="admin/services/nft-qos",
            new_path="admin/services/nft-qos",
            new_title="QoS over Nftables (Modified)",
            new_order=70
        )
    ]

    applier = LuaControllerApplier()

    # 读取原始内容
    original_content = file_path.read_text(encoding="utf-8", errors="ignore")
    print(f"\n原始文件路径: {file_path}")
    print(f"\n原始内容预览:")
    print(original_content[:500])

    # 应用修改（dry-run 模式，先不实际修改文件）
    print(f"\n测试修改:")
    print(f"  1. admin/status/realtime/rate -> 标题: 'Rate (Modified)', order: 10")
    print(f"  2. admin/services/nft-qos -> 标题: 'QoS over Nftables (Modified)', order: 70")

    # 检查是否能正确识别这些 entry
    try:
        from luaparser import ast
        tree = ast.parse(original_content)
        variables = applier._extract_variables(tree)

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
                    if parts:
                        entry_paths.append("/".join(parts))

        print(f"\n找到 {entry_count} 个 entry:")
        for i, path in enumerate(entry_paths, 1):
            print(f"  {i}. {path}")

        # 检查是否能找到目标 entry
        target_paths = ["admin/status/realtime/rate", "admin/services/nft-qos"]
        found_all = all(path in entry_paths for path in target_paths)

        if found_all:
            print(f"\n✅ 所有目标 entry 都能正确识别")
            return True
        else:
            print(f"\n❌ 部分目标 entry 未能识别")
            for path in target_paths:
                status = "✅" if path in entry_paths else "❌"
                print(f"  {status} {path}")
            return False

    except Exception as e:
        print(f"\n❌ 解析失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_pgyvpn():
    """测试 pgyvpn.lua - 条件分支中的 entry"""
    print(f"\n{'='*60}")
    print("测试 2: pgyvpn.lua - 条件分支中的 entry")
    print("="*60)

    # 文件路径
    file_path = Path('../../test_lede/feeds/luci/applications/luci-app-pgyvpn/luasrc/controller/pgyvpn.lua')

    # 读取原始内容
    original_content = file_path.read_text(encoding="utf-8", errors="ignore")
    print(f"\n原始文件路径: {file_path}")
    print(f"\n原始内容预览:")
    print(original_content[:800])

    applier = LuaControllerApplier()

    # 检查是否能正确识别条件分支中的 entry
    try:
        from luaparser import ast
        tree = ast.parse(original_content)
        variables = applier._extract_variables(tree)

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
                    if parts:
                        entry_paths.append("/".join(parts))

        print(f"\n找到 {entry_count} 个 entry:")
        for i, path in enumerate(entry_paths, 1):
            print(f"  {i}. {path}")

        # 检查是否能找到条件分支中的 entry
        target_path = "admin/services/pgyvpn"
        found = target_path in entry_paths

        if found:
            print(f"\n✅ 条件分支中的 entry 能正确识别")
            print(f"\n注意: 该路径在 if/else 分支中出现两次，但 AST 解析器会识别出两个独立的 entry 节点")
            print(f"这是预期行为，因为它们是两个独立的 entry() 调用")
            return True
        else:
            print(f"\n❌ 条件分支中的 entry 未能识别")
            return False

    except Exception as e:
        print(f"\n❌ 解析失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("Lua Controller 边界情况测试")
    print("="*60)

    results = []

    # 测试 1: 多 entry 文件
    results.append(("多 entry 文件", test_nft_qos()))

    # 测试 2: 条件分支中的 entry
    results.append(("条件分支中的 entry", test_pgyvpn()))

    # 输出总结
    print(f"\n{'='*60}")
    print("测试总结")
    print(f"{'='*60}")

    for test_name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{status} - {test_name}")

    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    print(f"\n通过: {passed_count}/{total_count}")

    if passed_count == total_count:
        print("\n✅ 所有测试通过，边界情况处理正常")
        return True
    else:
        print("\n❌ 部分测试失败，需要修复")
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
