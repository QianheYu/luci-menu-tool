
import sys
import json
from pathlib import Path

# 确保父目录在路径中，以便导入LuciMenuTool
sys.path.insert(0, '../..')

from LuciMenuTool.main import _extract_changes
from LuciMenuTool.lua_controller.applier import LuaControllerApplier

# Load modified export
with open('/tmp/test_apply_modified.json', 'r') as f:
    data = json.load(f)

pkg = data['luci-app-cpulimit']
source = pkg['source']
file_path = pkg['file']
menu_trees = pkg['menu_trees']

print(f"Package: luci-app-cpulimit")
print(f"Source: {source}")
print(f"File: {file_path}")

# Extract changes
changes = _extract_changes(menu_trees)
print(f"Changes extracted: {len(changes)}")
for change in changes:
    print(f"  - {change.old_path}: order={change.new_order}")

# Apply changes
source_path = Path('../../test_lede/feeds/luci/applications/luci-app-cpulimit') / file_path
print(f"Source path: {source_path}")
print(f"File exists: {source_path.exists()}")

# Backup original
import shutil
backup = Path('/tmp/cpulimit-orig.lua')
shutil.copy2(source_path, backup)
print(f"Backup created at {backup}")

# Apply
applier = LuaControllerApplier()
applier.apply(source_path, changes)

# Compare
with open(backup, 'r') as f:
    original = f.read()
with open(source_path, 'r') as f:
    modified = f.read()

if original == modified:
    print("ERROR: File unchanged!")
else:
    print("SUCCESS: File modified")
    # Show diff
    import difflib
    diff = list(difflib.unified_diff(original.splitlines(), modified.splitlines(), lineterm=''))
    for line in diff[:20]:
        print(line)
    if len(diff) > 20:
        print(f"... and {len(diff) - 20} more lines")

# Restore backup
shutil.copy2(backup, source_path)
print("Original file restored")
