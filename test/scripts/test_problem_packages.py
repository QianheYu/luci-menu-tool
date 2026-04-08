#!/usr/bin/env python3
import json

# 读取导出的文件
with open("/tmp/menu_export.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# 只选择已知有问题的包
test_packages = ["luci-app-cpulimit", "luci-app-arpbind", "luci-app-oscam"]

for pkg_name in test_packages:
    if pkg_name in data:
        pkg = data[pkg_name]
        print(f"\nPackage: {pkg_name}")
        print(f"Source: {pkg.get('source')}")
        print(f"File: {pkg.get('file')}")
        for tree in pkg.get("menu_trees", []):
            root_path = tree.get("root_path", "")
            print(f"  Root: {root_path}")
            print(f"    Title: {tree.get('root_title')}")
            print(f"    Order: {tree.get('root_order')}")

            # 添加修改
            if tree.get("root_order"):
                tree["root_new_order"] = "999"
            if tree.get("root_title"):
                tree["root_new_title"] = tree["root_title"] + " [Test]"

# 保存修改后的文件
with open("/tmp/test_problem_override.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print("\nCreated test_problem_override.json")
