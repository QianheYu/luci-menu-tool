
"""
测试已知问题包的应用功能
验证 luci-app-cpulimit、luci-app-arpbind、luci-app-oscam 的实际应用情况
"""
import json
import sys
import os
from pathlib import Path

# 确保父目录在路径中，以便导入LuciMenuTool
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from LuciMenuTool.lua_controller.applier import LuaControllerApplier
from LuciMenuTool.core.models import Change

def test_package(package_name, test_data):
    """测试单个包的应用功能"""
    print(f"\n{'='*60}")
    print(f"测试包: {package_name}")
    print(f"{'='*60}")

    # 创建应用器
    applier = LuaControllerApplier()

    # 获取文件路径
    base_path = Path(__file__).parent.parent.parent / 'test_lede'
    pkg_path = test_data['pkg_path'].replace('test_lede/', '')
    source_path = base_path / pkg_path / test_data['file']
    print(f"源文件: {source_path}")

    if not source_path.exists():
        print(f"❌ 文件不存在: {source_path}")
        return False

    # 读取原始内容
    original_content = source_path.read_text(encoding='utf-8')
    print(f"\n原始内容:\n{original_content}")

    # 创建测试修改
    changes = []
    for menu_tree in test_data['menu_trees']:
        change = Change(
            old_path=menu_tree['root_path'],
            new_path=menu_tree['root_path'] + '_test',
            new_title=f"{menu_tree['root_title']} (Test)" if menu_tree['root_title'] else None,
            new_order=int(menu_tree['root_order']) + 1 if menu_tree['root_order'] else None
        )
        changes.append(change)
        print(f"\n测试修改:")
        print(f"  路径: {change.old_path} -> {change.new_path}")
        print(f"  标题: {menu_tree['root_title']} -> {change.new_title}")
        print(f"  排序: {menu_tree['root_order']} -> {change.new_order}")

    # 应用修改
    try:
        applier.apply(source_path, changes)

        # 读取修改后的内容
        modified_content = source_path.read_text(encoding='utf-8')
        print(f"\n修改后内容:\n{modified_content}")

        # 验证修改
        success = True
        for change in changes:
            if change.new_path:
                # 路径的各个部分是分开存储的，需要检查每个部分
                path_parts = change.new_path.split("/")
                for part in path_parts:
                    if f'"{part}"' not in modified_content:
                        print(f"❌ 路径修改失败: {part} 未找到")
                        success = False
            if change.new_title and change.new_title not in modified_content:
                print(f"❌ 标题修改失败: {change.new_title} 未找到")
                success = False
            if change.new_order and str(change.new_order) not in modified_content:
                print(f"❌ 排序修改失败: {change.new_order} 未找到")
                success = False

        if success:
            print(f"\n✅ {package_name} 测试通过")
        else:
            print(f"\n❌ {package_name} 测试失败")

        # 恢复原始内容
        source_path.write_text(original_content, encoding='utf-8')

        return success
    except Exception as e:
        print(f"❌ 应用修改时出错: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主测试函数"""
    # 加载导出的菜单信息
    export_file = Path(__file__).parent.parent.parent / 'menu_export.json'
    with open(export_file, 'r', encoding='utf-8') as f:
        menu_data = json.load(f)

    # 测试的包列表
    test_packages = ['luci-app-cpulimit', 'luci-app-arpbind', 'luci-app-oscam']

    results = {}
    for package_name in test_packages:
        if package_name in menu_data:
            results[package_name] = test_package(package_name, menu_data[package_name])
        else:
            print(f"\n❌ 未找到包: {package_name}")
            results[package_name] = False

    # 输出总结
    print(f"\n{'='*60}")
    print("测试总结")
    print(f"{'='*60}")
    for package_name, success in results.items():
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{package_name}: {status}")

    # 返回测试结果
    all_passed = all(results.values())
    sys.exit(0 if all_passed else 1)

if __name__ == '__main__':
    main()
