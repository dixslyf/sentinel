from collections.abc import Collection

from sentinel_server.plugins import PluginManager

plugin_manager: PluginManager


def init_plugin_manager(plugin_whitelist: Collection[str]):
    global plugin_manager
    plugin_manager = PluginManager(plugin_whitelist)
