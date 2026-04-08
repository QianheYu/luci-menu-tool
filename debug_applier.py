import sys
sys.path.insert(0, '.')
from pathlib import Path
from LuciMenuTool.core.models import Change
from LuciMenuTool.lua_controller.applier import LuaControllerApplier

source_path = Path('./test_lede/feeds/luci/applications/luci-app-nft-qos/luasrc/controller/nft-qos.lua')
changes = [
    Change(
        old_path='admin/services/nft-qos',
        new_path=None,
        new_title=None,
        new_order='71',
        new_alias=None
    )
]

applier = LuaControllerApplier()
applier.apply(source_path, changes)
print("Applied changes")