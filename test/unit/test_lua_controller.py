import tempfile
from pathlib import Path

from LuciMenuTool.lua_controller.parser import LuaControllerParser
from LuciMenuTool.lua_controller.applier import LuaControllerApplier
from LuciMenuTool.core.models import Change


def test_lua_parser_entry_basic():
    content = """
module("luci.controller.test", package.seeall)

function index()
    entry({"admin", "services", "testapp"}, cbi("testapp"), _("Test App"), 30)
end
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.lua', delete=False) as f:
        f.write(content)
        f.flush()
        path = Path(f.name)

    parser = LuaControllerParser()
    entries = parser.parse(path)

    assert len(entries) == 1
    assert entries[0].path == "admin/services/testapp"
    assert entries[0].title == "Test App"
    assert entries[0].order == "30"
    path.unlink()
    print("test_lua_parser_entry_basic PASSED")


def test_lua_parser_entry_alias():
    content = """
module("luci.controller.test", package.seeall)

function index()
    entry({"admin", "services", "minieap"}, alias("admin", "services", "minieap", "general"), _("Minieap"), 10)
    entry({"admin", "services", "minieap", "general"}, cbi("minieap"), _("General"), 1)
    entry({"admin", "services", "minieap", "status"}, call("action_status")).leaf = true
end
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.lua', delete=False) as f:
        f.write(content)
        f.flush()
        path = Path(f.name)

    parser = LuaControllerParser()
    entries = parser.parse(path)

    assert len(entries) == 3
    root = next(e for e in entries if e.path == "admin/services/minieap")
    assert root.alias == "admin/services/minieap/general"
    assert root.title == "Minieap"
    assert root.order == "10"
    path.unlink()
    print("test_lua_parser_entry_alias PASSED")


def test_lua_parser_entry_variable():
    content = """
module("luci.controller.passwall", package.seeall)

function index()
    local appname = "passwall"
    entry({"admin", "services", appname}, alias("admin", "services", appname, "settings"), _("Pass Wall"), -1)
    entry({"admin", "services", appname, "settings"}, cbi(appname .. "/client/global"), _("Basic Settings"), 1)
end
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.lua', delete=False) as f:
        f.write(content)
        f.flush()
        path = Path(f.name)

    parser = LuaControllerParser()
    entries = parser.parse(path)

    assert len(entries) == 2
    root = next(e for e in entries if e.path == "admin/services/passwall")
    assert root.title == "Pass Wall"
    assert root.order == "-1"
    assert root.alias == "admin/services/passwall/settings"

    child = next(e for e in entries if e.path == "admin/services/passwall/settings")
    assert child.title == "Basic Settings"
    assert child.order == "1"
    path.unlink()
    print("test_lua_parser_entry_variable PASSED")


def test_lua_parser_entry_no_title():
    content = """
module("luci.controller.test", package.seeall)

function index()
    entry({"admin", "services", "test"}, call("action_status")).leaf = true
end
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.lua', delete=False) as f:
        f.write(content)
        f.flush()
        path = Path(f.name)

    parser = LuaControllerParser()
    entries = parser.parse(path)

    assert len(entries) == 1
    assert entries[0].path == "admin/services/test"
    assert entries[0].title is None
    path.unlink()
    print("test_lua_parser_entry_no_title PASSED")


def test_lua_parser_node():
    content = """
module("luci.controller.cshark", package.seeall)

function index()
    page = node("admin", "network", "cloudshark")
    page.target = cbi("admin_network/cshark")
    page.title = _("CloudShark")
    page.order = 70
end
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.lua', delete=False) as f:
        f.write(content)
        f.flush()
        path = Path(f.name)

    parser = LuaControllerParser()
    entries = parser.parse(path)

    assert len(entries) == 1
    assert entries[0].path == "admin/network/cloudshark"
    assert entries[0].title == "CloudShark"
    assert entries[0].order == "70"
    path.unlink()
    print("test_lua_parser_node PASSED")


def test_lua_parser_dedup():
    content = """
module("luci.controller.test", package.seeall)

function index()
    if condition then
        entry({"admin", "services", "test"}, cbi("test"), _("Test"), 10)
    else
        entry({"admin", "services", "test"}, cbi("test"), nil, 10)
    end
end
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.lua', delete=False) as f:
        f.write(content)
        f.flush()
        path = Path(f.name)

    parser = LuaControllerParser()
    entries = parser.parse(path)

    assert len(entries) == 1
    assert entries[0].title == "Test"
    assert entries[0].order == "10"
    path.unlink()
    print("test_lua_parser_dedup PASSED")


def test_lua_applier_path_change():
    content = """module("luci.controller.test", package.seeall)

function index()
    entry({"admin", "services", "old"}, cbi("test"), _("Test"), 10)
end
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.lua', delete=False) as f:
        f.write(content)
        f.flush()
        path = Path(f.name)

    applier = LuaControllerApplier()
    applier.apply(path, [Change(old_path="admin/services/old", new_path="admin/services/new")])

    result = path.read_text()
    assert '"admin", "services", "new"' in result
    assert '"old"' not in result
    path.unlink()
    print("test_lua_applier_path_change PASSED")


def test_lua_applier_order_change():
    content = """module("luci.controller.test", package.seeall)

function index()
    entry({"admin", "services", "test"}, cbi("test"), _("Test"), 10)
end
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.lua', delete=False) as f:
        f.write(content)
        f.flush()
        path = Path(f.name)

    applier = LuaControllerApplier()
    applier.apply(path, [Change(old_path="admin/services/test", new_order="50")])

    result = path.read_text()
    assert '50)' in result
    path.unlink()
    print("test_lua_applier_order_change PASSED")


def test_lua_applier_title_change():
    content = """module("luci.controller.test", package.seeall)

function index()
    entry({"admin", "services", "test"}, cbi("test"), _("Old Title"), 10)
end
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.lua', delete=False) as f:
        f.write(content)
        f.flush()
        path = Path(f.name)

    applier = LuaControllerApplier()
    applier.apply(path, [Change(old_path="admin/services/test", new_title="New Title")])

    result = path.read_text()
    assert 'New Title' in result
    assert 'Old Title' not in result
    path.unlink()
    print("test_lua_applier_title_change PASSED")


if __name__ == "__main__":
    test_lua_parser_entry_basic()
    test_lua_parser_entry_alias()
    test_lua_parser_entry_variable()
    test_lua_parser_entry_no_title()
    test_lua_parser_node()
    test_lua_parser_dedup()
    test_lua_applier_path_change()
    test_lua_applier_order_change()
    test_lua_applier_title_change()
    print("\nAll lua_controller tests PASSED!")
