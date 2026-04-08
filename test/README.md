# LuciMenuTool 测试目录

本目录包含LuciMenuTool项目的所有测试代码和测试辅助脚本。

## 目录结构

```
test/
├── __init__.py
├── README.md
├── unit/              # 单元测试
│   ├── __init__.py
│   ├── test_lua_controller.py    # Lua控制器解析器和应用器测试
│   ├── test_menu_d.py            # menu.d JSON解析器和应用器测试
│   └── test_ucode_controller.py # uCode控制器解析器和应用器测试
├── integration/       # 集成测试
│   ├── __init__.py
│   └── test_apply.py              # 完整的应用流程测试
└── scripts/           # 测试辅助脚本
    ├── __init__.py
    ├── test_modify.py             # 测试菜单修改
    └── test_problem_packages.py   # 测试已知问题的包
```

## 测试分类

### 单元测试 (unit/)

单元测试用于测试各个组件的独立功能，包括：
- Lua控制器的解析和应用
- menu.d JSON的解析和应用
- uCode控制器的解析和应用

运行单元测试：
```bash
# 运行所有单元测试
python -m pytest test/unit/

# 运行特定测试文件
python test/unit/test_lua_controller.py
python test/unit/test_menu_d.py
python test/unit/test_ucode_controller.py
```

### 集成测试 (integration/)

集成测试用于测试完整的业务流程，验证各个组件协同工作的正确性。

运行集成测试：
```bash
python test/integration/test_apply.py
```

### 测试辅助脚本 (scripts/)

这些脚本用于辅助测试和验证特定功能。

运行测试脚本：
```bash
python test/scripts/test_modify.py
python test/scripts/test_problem_packages.py
```

## 注意事项

1. 所有测试文件都应遵循Python的命名规范：`test_*.py`
2. 运行测试前，请确保已安装所有必要的依赖
3. 集成测试可能会修改实际的文件，请确保在测试环境中运行
4. 测试辅助脚本可能需要特定的输入文件，请根据脚本中的路径准备相应的测试数据
