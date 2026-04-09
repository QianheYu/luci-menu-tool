# LuCI 菜单路径管理工具 - 设计文档

## 1. 项目背景

### 1.1 需求来源

在 OpenWrt/LEDE 固件定制过程中，LuCI 是默认的 Web 管理界面。第三方软件包通过不同的方式定义菜单路径和排序序号，导致：
- 菜单路径分散，难以统一管理
- 排序序号冲突或不符合定制需求
- 修改菜单需要手动编辑多个文件，容易出错

### 1.2 工具目标

提供一个 Python 工具，能够：
1. **提取**：扫描所有 luci-app-* 软件包，提取完整的菜单路径和排序序号
2. **导出**：保存为结构化的 JSON 文件
3. **覆盖**：修改 JSON 文件后，自动应用更改到源文件

## 2. LuCI 菜单定义方式

### 2.1 menu.d JSON 文件（推荐/现代方式）

**位置：**
- `root/usr/share/luci/menu.d/<name>.json`
- `luasrc/luci/menu.d/<name>.json`（旧布局）

**示例：**
```json
{
  "admin/services/ttyd": {
    "title": "Terminal",
    "order": 1,
    "action": { "type": "firstchild" }
  },
  "admin/services/ttyd/ttyd": {
    "title": "Terminal",
    "order": 10,
    "action": { "type": "view", "path": "ttyd/term" }
  },
  "admin/services/ttyd/config": {
    "title": "Config",
    "order": 2,
    "action": { "type": "view", "path": "ttyd/config" }
  }
}
```

**特点：**
- 声明式，易于解析
- 支持 alias 类型指向其他路径
- 支持 firstchild 类型自动选择第一个子项

### 2.2 Lua Controller - entry() 方式

**位置：** `luasrc/controller/<name>.lua`

**示例：**
```lua
function index()
  entry({"admin", "services", "myapp"}, alias("admin", "services", "myapp", "settings"), _("My App"), 30)
  entry({"admin", "services", "myapp", "settings"}, cbi("myapp/settings"), _("Settings"), 10)
  entry({"admin", "services", "myapp", "status"}, call("action_status")).leaf = true
end
```

**entry() 参数：**
1. 路径数组：`{"admin", "services", "myapp"}`
2. 目标函数：`alias()`, `cbi()`, `call()`, `form()`, `template()`, `firstchild()`
3. 标题：`_("标题")` 或 `"标题"` 或 `nil`
4. 排序序号：数字（可选，支持负数）

**特点：**
- 支持变量：`entry({"admin", "services", appname}, ...)`
- 支持 if/else 分支，可能产生重复 entry
- 支持字符串拼接：`"check_" .. com`（应跳过）
- 支持 `e = entry(...)` 赋值形式，后续可设置 `e.order = N`

### 2.3 Lua Controller - node() 方式

**位置：** `luasrc/controller/<name>.lua`

**示例：**
```lua
function index()
  page = node("admin", "network", "cloudshark")
  page.target = cbi("admin_network/cshark")
  page.title = _("CloudShark")
  page.order = 70
  page.acl_depends = { "luci-app-cshark" }
end
```

**特点：**
- 通过 `page.title = _("...")` 设置标题
- 通过 `page.order = N` 设置排序
- 变量名不固定（可以是 `page`、`node` 等）

### 2.4 UCode Controller（最新方式）

**位置：** `ucode/controller/<name>.uc`

**示例：**
```js
import { entry, alias } from "luci.dispatcher";
entry(["admin", "services", "myapp"], alias("..."), _("My App"), 30);
```

**注意：** 当前工具暂不支持 UCode 格式。

### 2.5 特殊情况

#### 2.5.1 多父菜单路径

某些软件包（如 mwan3）在多个父菜单下都有入口：

```json
{
  "admin/network/mwan3": { "title": "MultiWAN Manager", "order": 600 },
  "admin/status/mwan3": { "title": "MultiWAN Manager", "order": 600 }
}
```

#### 2.5.2 Alias 路径

menu.d 和 Lua controller 都支持 alias：

**menu.d:**
```json
{
  "admin/services/polipo": {
    "title": "Polipo",
    "action": { "type": "alias", "path": "admin/services/polipo/config" }
  }
}
```

**Lua controller:**
```lua
entry({"admin", "services", "minieap"}, alias("admin", "services", "minieap", "general"), _("Minieap"), 10)
```

#### 2.5.3 变量引用

```lua
local appname = "passwall"
entry({"admin", "services", appname}, alias("admin", "services", appname, "settings"), _("Pass Wall"), -1)
```

**特殊变量定义：**
```lua
local api = require "luci.passwall.api"
local appname = api.appname  -- 需要从包名推断
```

#### 2.5.4 if/else 分支

```lua
if uci:get(appname, "@global[0]", "hide_from_luci") ~= "1" then
  e = entry({"admin", "services", appname}, alias(...), _("Pass Wall"), -1)
else
  e = entry({"admin", "services", appname}, alias(...), nil, -1)
end
```

## 3. JSON 数据结构设计

### 3.1 整体结构

```json
{
  "luci-app-<name>": {
    "source": "menu.d | controller | unknown",
    "file": "相对路径",
    "makefile_category": "",
    "makefile_submenu": "",
    "makefile_priority": "",
    "menu_trees": [...]
  }
}
```

### 3.2 menu_trees 数组

每个顶级菜单路径为一棵树：

```json
{
  "root_path": "admin/services/myapp",
  "root_title": "My App",
  "root_order": "30",
  "root_alias": "admin/services/myapp/settings",
  "children": [
    {
      "path": "admin/services/myapp/settings",
      "title": "Settings",
      "order": "10",
      "alias": ""
    }
  ]
}
```

### 3.3 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `source` | string | 菜单定义方式：`menu.d`、`controller`、`unknown` |
| `file` | string | 源文件相对路径 |
| `root_path` | string | 顶级菜单路径 |
| `root_title` | string | 顶级菜单标题 |
| `root_order` | string | 顶级菜单排序序号 |
| `root_alias` | string | 顶级菜单 alias 路径（可选） |
| `children` | array | 子菜单项列表 |
| `children[].path` | string | 子菜单完整路径 |
| `children[].title` | string | 子菜单标题 |
| `children[].order` | string | 子菜单排序序号 |
| `children[].alias` | string | 子菜单 alias 路径（可选） |

### 3.4 覆盖修改字段

修改时可使用以下额外字段：

| 字段 | 说明 |
|------|------|
| `new_path` | 新的子菜单路径 |
| `root_new_path` | 新的顶级菜单路径 |
| `new_alias` | 新的子菜单 alias 路径 |
| `root_new_alias` | 新的顶级菜单 alias 路径 |

## 4. 工具设计流程

### 4.1 扫描流程

```
开始
  ↓
扫描 luci-app-* 目录（支持递归）
  ↓
对每个包：
  ├─ 解析 Makefile（提取 CATEGORY、SUBMENU、PRIORITY）
  ├─ 检查 menu.d 目录
  │   ├─ 查找 root/usr/share/luci/menu.d/*.json
  │   ├─ 查找 luasrc/luci/menu.d/*.json
  │   └─ 解析 JSON 文件，提取 entries
  ├─ 如果无 menu.d，检查 controller 目录
  │   ├─ 查找 luasrc/controller/*.lua
  │   ├─ 提取变量定义
  │   ├─ 解析 entry() 调用
  │   ├─ 解析 node() 调用
  │   └─ 提取 title、order、alias
  └─ 构建 menu_trees 结构
        ↓
导出 JSON 文件
```

### 4.2 解析关键逻辑

#### 4.2.1 entry() 解析

```python
# 正则匹配 entry({...},
entry_matches = re.finditer(r'entry\s*\(\s*\{([^}]+)\}\s*,', content)

# 括号计数找闭合
depth = 1
for ch in after_bracket:
    if ch == '(': depth += 1
    elif ch == ')':
        depth -= 1
        if depth == 0: end_pos = i; break

# 提取 entry_scope
entry_scope = after_bracket[:end_pos]

# 替换目标函数为 TARGET
cleaned_scope = re.sub(r'(alias|cbi|call|form|template|firstchild|arcombine)\s*\([^)]*\)', 'TARGET', entry_scope)

# 提取 title
title_match = re.search(r'TARGET\s*,\s*_\(\s*"([^"]+)"\s*\)', cleaned_scope)

# 提取 order
order_match = re.search(r',\s*(-?\d+)\s*$', entry_tail)
```

#### 4.2.2 node() 解析

```python
# 正则匹配 var = node(...)
node_matches = re.finditer(r'(\w+)\s*=\s*node\s*\(\s*([^)]+)\)', content)

# 提取 title 和 order
title_match = re.search(rf'{var_name}\.title\s*=\s*_\(\s*"([^"]+)"\s*\)', content)
order_match = re.search(rf'{var_name}\.order\s*=\s*(\d+)', content)
```

#### 4.2.3 变量解析

```python
# 简单字符串赋值
var_matches = re.findall(r'local\s+(\w+)\s*=\s*["\']([^"\']+)["\']', content)

# 过滤尾随反斜杠（避免 bad escape 错误）
if var_value and not var_value.endswith('\\'):
    variables[var_name] = var_value

# 从包名推断 appname
if 'appname' not in variables:
    if re.search(r'api\.appname|luci\.\w+\.appname', content):
        variables['appname'] = pkg_name.replace('luci-app-', '')

# 替换变量时使用 lambda 避免转义问题
resolved_path = re.sub(r'\b' + re.escape(var_name) + r'\b', lambda m: var_value, path_str)
```

#### 4.2.4 去重逻辑

```python
seen_paths = {}
for entry in entries:
    if full_path in seen_paths:
        # 合并信息：优先保留非空值
        existing = seen_paths[full_path]
        if not existing.get("title") and entry_info.get("title"):
            existing["title"] = entry_info["title"]
        if not existing.get("order") and entry_info.get("order"):
            existing["order"] = entry_info["order"]
        if not existing.get("alias") and entry_info.get("alias"):
            existing["alias"] = entry_info["alias"]
    else:
        seen_paths[full_path] = entry_info
```

### 4.3 应用覆盖流程

```
开始
  ↓
加载覆盖 JSON 文件
  ↓
对每个包：
  ├─ 查找包目录（优先使用扫描时记录的路径）
  ├─ 根据 source 类型选择更新方式
  ├─ menu.d 类型：
  │   ├─ 查找包含 JSON 文件的 menu.d 目录
  │   ├─ 加载 JSON 文件
  │   ├─ 匹配路径或 title
  │   ├─ 更新 path、title、order、alias
  │   └─ 写回 JSON 文件
  └─ controller 类型：
      ├─ 查找 controller 目录
      ├─ 加载 Lua 文件
      ├─ 预解析所有 entry/node 匹配
      ├─ 收集所有编辑操作
      ├─ 按位置倒序应用编辑
      └─ 写回 Lua 文件
  ↓
完成
```

### 4.4 Lua 文件更新关键逻辑

```python
# 预解析所有匹配
entry_parsed = []
for match_obj in entry_matches:
    entry_parsed.append({
        "match_obj": match_obj,
        "path": full_path,
        "parts": [...],
        "resolved_parts": [...],
        "order": order_val,
        "alias": alias_val,
        "after_bracket": after_bracket,
        "end_pos": end_pos
    })

# 收集所有编辑
edits = []
for item in all_items:
    for ep in entry_parsed:
        if match:
            if path_changed:
                edits.append((start, end, new_str))
            if order_changed:
                edits.append((order_start, order_end, new_order))
            if alias_changed:
                edits.append((alias_start, alias_end, new_alias))

# 倒序应用编辑（避免位置偏移）
edits.sort(key=lambda x: x[0], reverse=True)
for start, end, replacement in edits:
    content = content[:start] + replacement + content[end:]
```

## 5. 测试流程

### 5.1 测试环境准备

```bash
# 1. 克隆 LEDE 仓库
git clone https://github.com/coolsnowwolf/lede.git ./test_lede

# 2. 更新 feeds
./test_lede/scripts/feeds update luci

# 3. 安装 luci 软件包
./test_lede/scripts/feeds install -a -p luci
```

### 5.2 功能测试

#### 5.2.1 扫描测试

```bash
python3 luci_menu_tool.py --scan ./test_lede/feeds/luci/applications
```

**验证点：**
- 扫描到所有 181 个 luci-app-* 包
- 正确识别 source 类型（menu.d / controller / unknown）
- 无解析错误

#### 5.2.2 导出测试

```bash
python3 luci_menu_tool.py --scan ./test_lede/feeds/luci/applications --export -o menu_export.json
```

**验证点：**
- 生成有效的 JSON 文件
- 所有包都有正确的结构
- menu_trees 正确构建

#### 5.2.3 应用测试

```bash
# 1. 创建覆盖文件
# 2. 应用覆盖
python3 luci_menu_tool.py --scan ./test_lede/feeds/luci/applications --apply -i override.json

# 3. 验证源文件被正确修改
```

**验证点：**
- menu.d JSON 文件正确更新
- Lua controller 文件正确更新
- 路径、title、order、alias 都正确修改

### 5.3 关键包验证

| 包名 | 验证点 |
|------|--------|
| luci-app-mwan3 | 多父菜单路径（admin/network + admin/status） |
| luci-app-passwall | 变量解析、alias 提取、root title/order |
| luci-app-passwall2 | 同上 |
| luci-app-minieap | alias 提取（entry 第三个参数） |
| luci-app-cshark | node() 方式的 title/order 提取 |
| luci-app-ltqtapi | node() 方式的 title/order 提取 |
| luci-app-nft-qos | entry() 的 order 提取 |
| luci-app-unbound | if/else 分支去重 |
| luci-app-scutclient | if/else 分支去重 |
| luci-app-openclash | 大量 call() 子项（无 title） |
| luci-app-dockerman | form()/call() 子项（无 title） |

### 5.4 边界情况测试

| 场景 | 预期行为 |
|------|----------|
| 字符串拼接路径（`"check_" .. com`） | 跳过，不提取 |
| 尾随反斜杠变量（`HOME=\"..configdir`） | 过滤，避免 bad escape |
| 未定义的 appname 变量 | 从包名推断 |
| 重复 entry（if/else） | 合并，保留非空值 |
| 负数 order（`-1`） | 正确提取 |
| 无 title 的 entry（`call()`） | title 为空字符串 |
| 包在子目录中 | 递归扫描找到 |

## 6. 关键设计决策

### 6.1 为什么使用 menu_trees 结构？

**问题：** 原始设计使用 `full_path`（单字符串）和 `priority`（单值），无法表达：
- 多父菜单路径（如 mwan3）
- 每个子项独立的 order
- 层级关系

**解决方案：** 使用 `menu_trees` 数组，每个顶级路径为一棵树，包含独立的 `root_*` 字段和 `children` 数组。

### 6.2 为什么 alias 放在 root 级别？

alias 是顶级菜单的属性，表示点击后跳转到的路径。放在 `root_alias` 字段中，与 `root_path`、`root_title`、`root_order` 同级，便于理解和修改。

### 6.3 为什么使用倒序编辑？

修改文件内容会导致后续位置偏移。收集所有编辑后按位置倒序应用，确保每个编辑的位置引用仍然有效。

### 6.4 为什么 entry_scope 需要括号计数？

`entry()` 的第二个参数可能是嵌套函数调用，如 `alias("admin", "services", appname, "settings")`。简单的 `[^)]*` 会错误匹配到嵌套的 `)`。使用括号计数确保找到正确的闭合 `)`。

### 6.5 为什么 title 提取需要替换 TARGET？

`entry()` 的第三个参数是 title，但第二个参数可能是 `cbi("...")`、`call("...")` 等函数。直接搜索 `"..."` 会匹配到函数参数。先将所有函数调用替换为 `TARGET`，再搜索 `TARGET, _("title")` 确保准确定位 title。

## 7. 命令行接口

```bash
# 扫描并显示摘要
python3 luci_menu_tool.py --scan <feed_path>

# 扫描并导出到文件
python3 luci_menu_tool.py --scan <feed_path> --export -o output.json

# 应用覆盖（实际修改）
python3 luci_menu_tool.py --scan <feed_path> --apply -i override.json

# 预览覆盖（不修改）
python3 luci_menu_tool.py --scan <feed_path> --apply -i override.json --dry-run
```

## 8. 已知限制

1. **不支持 UCode controller**（`.uc` 文件）
2. **不解析复杂的 Lua 表达式**（如动态生成的路径）
3. **不处理多行 entry() 调用**（少数包使用）
4. **Makefile 中的 LUCI_CATEGORY/SUBMENU/ORDER 不提取**（这些影响 menuconfig，不影响 Web UI）

## 9. 文件结构

```
luci_menu_tool.py
├── LuCIMenuTool 类
│   ├── __init__(feed_path)
│   ├── scan_packages()          # 扫描所有包
│   ├── _process_package()       # 处理单个包
│   ├── _parse_makefile()        # 解析 Makefile
│   ├── _parse_menu_d()          # 解析 menu.d JSON
│   ├── _parse_controller()      # 解析 Lua controller
│   ├── _build_menu_trees()      # 构建树结构
│   ├── export_to_file()         # 导出 JSON
│   ├── apply_override()         # 应用覆盖
│   ├── _apply_menu_d_override() # 更新 menu.d
│   └── _apply_controller_override() # 更新 controller
└── main()                       # 命令行入口
```
