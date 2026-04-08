import tempfile
from pathlib import Path

from LuciMenuTool.ucode_controller.parser import UCodeControllerParser
from LuciMenuTool.ucode_controller.applier import UCodeControllerApplier
from LuciMenuTool.core.models import Change


def test_ucode_parser_basic():
    content = """
import { entry, cbi, translate as _ } from "luci.dispatcher";

entry(["admin", "services", "myapp"], cbi("myapp"), _("My App"), 30);
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.uc', delete=False) as f:
        f.write(content)
        f.flush()
        path = Path(f.name)

    parser = UCodeControllerParser()
    entries = parser.parse(path)

    assert len(entries) == 1
    assert entries[0].path == "admin/services/myapp"
    assert entries[0].title == "My App"
    assert entries[0].order == "30"
    path.unlink()
    print("test_ucode_parser_basic PASSED")


def test_ucode_applier_path_change():
    content = """
import { entry, cbi } from "luci.dispatcher";

entry(["admin", "services", "old"], cbi("test"), _("Test"), 10);
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.uc', delete=False) as f:
        f.write(content)
        f.flush()
        path = Path(f.name)

    applier = UCodeControllerApplier()
    applier.apply(path, [Change(old_path="admin/services/old", new_path="admin/services/new")])

    result = path.read_text()
    assert '"admin", "services", "new"' in result
    assert '"old"' not in result
    path.unlink()
    print("test_ucode_applier_path_change PASSED")


if __name__ == "__main__":
    test_ucode_parser_basic()
    test_ucode_applier_path_change()
    print("\nAll ucode_controller tests PASSED!")
