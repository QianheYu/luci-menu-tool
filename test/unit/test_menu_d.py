import json
import tempfile
from pathlib import Path

from LuciMenuTool.menu_d.parser import MenuDParser
from LuciMenuTool.menu_d.applier import MenuDApplier
from LuciMenuTool.core.models import Change


def test_menu_d_parser_basic():
    content = {
        "admin/services/test": {
            "title": "Test App",
            "order": 10,
            "action": {"type": "view", "path": "test"}
        },
        "admin/services/test/sub": {
            "title": "Sub Page",
            "order": 20
        }
    }
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(content, f)
        f.flush()
        path = Path(f.name)

    parser = MenuDParser()
    entries = parser.parse(path)

    assert len(entries) == 2
    assert entries[0].path == "admin/services/test"
    assert entries[0].title == "Test App"
    assert entries[0].order == "10"
    assert entries[1].path == "admin/services/test/sub"
    assert entries[1].order == "20"
    path.unlink()
    print("test_menu_d_parser_basic PASSED")


def test_menu_d_parser_alias():
    content = {
        "admin/services/polipo": {
            "title": "Polipo",
            "action": {"type": "alias", "path": "admin/services/polipo/config"}
        }
    }
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(content, f)
        f.flush()
        path = Path(f.name)

    parser = MenuDParser()
    entries = parser.parse(path)

    assert len(entries) == 1
    assert entries[0].alias == "admin/services/polipo/config"
    path.unlink()
    print("test_menu_d_parser_alias PASSED")


def test_menu_d_applier_path_change():
    content = {
        "admin/services/old": {"title": "Old", "order": 10}
    }
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(content, f)
        f.flush()
        path = Path(f.name)

    applier = MenuDApplier()
    applier.apply(path, [Change(old_path="admin/services/old", new_path="admin/services/new")])

    with open(path) as f:
        result = json.load(f)

    assert "admin/services/new" in result
    assert "admin/services/old" not in result
    assert result["admin/services/new"]["title"] == "Old"
    path.unlink()
    print("test_menu_d_applier_path_change PASSED")


def test_menu_d_applier_order_change():
    content = {
        "admin/services/test": {"title": "Test", "order": 10}
    }
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(content, f)
        f.flush()
        path = Path(f.name)

    applier = MenuDApplier()
    applier.apply(path, [Change(old_path="admin/services/test", new_order="50")])

    with open(path) as f:
        result = json.load(f)

    assert result["admin/services/test"]["order"] == 50
    path.unlink()
    print("test_menu_d_applier_order_change PASSED")


def test_menu_d_applier_alias_change():
    content = {
        "admin/services/test": {
            "title": "Test",
            "action": {"type": "alias", "path": "admin/services/test/old"}
        }
    }
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(content, f)
        f.flush()
        path = Path(f.name)

    applier = MenuDApplier()
    applier.apply(path, [Change(old_path="admin/services/test", new_alias="admin/services/test/new")])

    with open(path) as f:
        result = json.load(f)

    assert result["admin/services/test"]["action"]["path"] == "admin/services/test/new"
    path.unlink()
    print("test_menu_d_applier_alias_change PASSED")


if __name__ == "__main__":
    test_menu_d_parser_basic()
    test_menu_d_parser_alias()
    test_menu_d_applier_path_change()
    test_menu_d_applier_order_change()
    test_menu_d_applier_alias_change()
    print("\nAll menu_d tests PASSED!")
