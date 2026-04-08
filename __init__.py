from LuciMenuTool.core.registry import registry
from LuciMenuTool.menu_d import MenuDParser, MenuDApplier
from LuciMenuTool.lua_controller import LuaControllerParser, LuaControllerApplier
from LuciMenuTool.ucode_controller import UCodeControllerParser, UCodeControllerApplier

registry.register("menu.d", MenuDParser, MenuDApplier)
registry.register("controller", LuaControllerParser, LuaControllerApplier)
registry.register("ucode", UCodeControllerParser, UCodeControllerApplier)

__all__ = ["registry"]
