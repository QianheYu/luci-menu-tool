#!/usr/bin/env python3
import json

# 读取导出的文件
with open("/tmp/menu_export.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# 选择几个包进行修改
test_packages = ["luci-app-eoip", "luci-app-mosquitto", "luci-app-nft-qos"]

for pkg_name in test_packages:
    if pkg_name in data:
        pkg = data[pkg_name]
        for tree in pkg.get("menu_trees", []):
            root_path = tree.get("root_path", "")
            if root_path:
                # 修改根路径的order
                if tree.get("root_order"):
                    tree["root_new_order"] = "999"
                # 修改根路径的title
                if tree.get("root_title"):
                    tree["root_new_title"] = tree["root_title"] + " [Modified]"

                # 修改子菜单的order
                for child in tree.get("children", []):
                    if child.get("order"):
                        child["new_order"] = "888"

# 保存修改后的文件
with open("/tmp/menu_override.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print("Created menu_override.json with test modifications")
print(f"Modified packages: {test_packages}")
