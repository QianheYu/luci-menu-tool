
"""
测试 menu_d/applier.py 中的正则表达式字符显示问题
"""
import sys
import os
from pathlib import Path

# 确保父目录在路径中，以便导入LuciMenuTool
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from LuciMenuTool.menu_d.applier import MenuDApplier

def test_clean_duplicate_markers():
    """测试清理重复标记的功能"""
    print("="*60)
    print("测试 menu_d/applier.py 中的 _clean_duplicate_markers 方法")
    print("="*60)

    applier = MenuDApplier()

    # 测试用例
    test_cases = [
        {
            "input": "Title (Modified)",
            "expected": "Title (Modified)",
            "description": "单个标记，不应修改"
        },
        {
            "input": "Title (Modified) (Modified)",
            "expected": "Title (Modified)",
            "description": "重复的英文标记"
        },
        {
            "input": "Title (已修改)",
            "expected": "Title (已修改)",
            "description": "单个中文标记，不应修改"
        },
        {
            "input": "Title (已修改) (已修改)",
            "expected": "Title (已修改)",
            "description": "重复的中文标记"
        },
        {
            "input": "Title (Updated)",
            "expected": "Title (Updated)",
            "description": "单个 Updated 标记，不应修改"
        },
        {
            "input": "Title (Updated) (Updated)",
            "expected": "Title (Updated)",
            "description": "重复的 Updated 标记"
        },
        {
            "input": "Title (已更新)",
            "expected": "Title (已更新)",
            "description": "单个已更新标记，不应修改"
        },
        {
            "input": "Title (已更新) (已更新)",
            "expected": "Title (已更新)",
            "description": "重复的已更新标记"
        },
        {
            "input": "Title (Modified) (已修改)",
            "expected": "Title (Modified) (已修改)",
            "description": "不同的标记，不应修改"
        },
        {
            "input": "Title (Modified) (Modified) (Modified)",
            "expected": "Title (Modified)",
            "description": "多个重复标记"
        },
    ]

    # 执行测试
    results = []
    for i, test_case in enumerate(test_cases, 1):
        input_title = test_case["input"]
        expected = test_case["expected"]
        description = test_case["description"]

        result = applier._clean_duplicate_markers(input_title)
        passed = result == expected

        results.append({
            "test": i,
            "description": description,
            "input": input_title,
            "expected": expected,
            "result": result,
            "passed": passed
        })

        # 打印测试结果
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"\n测试 {i}: {description}")
        print(f"  输入: {input_title}")
        print(f"  期望: {expected}")
        print(f"  结果: {result}")
        print(f"  状态: {status}")

    # 输出总结
    print(f"\n{'='*60}")
    print("测试总结")
    print(f"{'='*60}")
    passed_count = sum(1 for r in results if r["passed"])
    total_count = len(results)
    print(f"通过: {passed_count}/{total_count}")

    if passed_count == total_count:
        print("\n✅ 所有测试通过，正则表达式工作正常")
        return True
    else:
        print("\n❌ 部分测试失败，需要修复")
        for r in results:
            if not r["passed"]:
                print(f"  - 测试 {r['test']}: {r['description']}")
        return False

if __name__ == '__main__':
    success = test_clean_duplicate_markers()
    sys.exit(0 if success else 1)
