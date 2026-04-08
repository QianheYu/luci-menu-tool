# LuciMenuTool

LuCI Menu Path and Priority Tool for OpenWrt/LEDE firmware customization.

## Features

- Scan all `luci-app-*` packages and extract menu paths, titles, orders, and aliases
- Export to structured JSON file
- Apply modifications from an edited JSON file back to source files
- Preserve original formatting (indentation, whitespace, line endings) with zero unnecessary file changes on re-apply
- Supports three menu definition methods: `menu.d` JSON, Lua Controller, and UCode Controller

## Installation

```bash
pip install luci-menu-tool
```

Or from source:

```bash
pip install .
```

## Usage

```bash
# Scan packages and show menu trees
luci-menu-tool --scan /path/to/feeds/luci/applications

# Export menu data to JSON
luci-menu-tool --scan /path/to/feeds/luci/applications --export -o menu_export.json

# Apply modifications from JSON file
luci-menu-tool --scan /path/to/feeds/luci/applications --apply -i override.json

# Dry-run to preview changes
luci-menu-tool --scan /path/to/feeds/luci/applications --apply -i override.json --dry-run
```

## JSON Format

The export JSON file has the following structure:

```json
{
  "luci-app-example": {
    "source": "menu.d",
    "file": "root/usr/share/luci/menu.d/luci-app-example.json",
    "menu_trees": [
      {
        "root_path": "admin/services/example",
        "root_title": "Example Service",
        "root_order": "600",
        "children": [
          {
            "path": "admin/services/example/config",
            "title": "Configuration",
            "order": "10"
          }
        ]
      }
    ]
  }
}
```

To modify a menu entry, add `new_*` fields:

```json
{
  "root_new_title": "New Title",
  "root_new_order": "700",
  "children": [
    {
      "path": "admin/services/example/config",
      "new_title": "New Config Title",
      "new_order": "20"
    }
  ]
}
```

## Development

```bash
# Install development dependencies
pip install -e .[dev]

# Run tests
pytest tests/

# Run automated apply test
python tests/test_apply.py
```

## Architecture

The tool is modular with three mode packages:

- `menu_d/`: JSON menu.d files
- `lua_controller/`: Lua controller files (AST-based parsing with luaparser)
- `ucode_controller/`: UCode controller files (LALR grammar with lark)

Each mode has a parser and applier that preserve original formatting.
