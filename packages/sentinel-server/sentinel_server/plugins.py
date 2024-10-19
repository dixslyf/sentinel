import importlib.metadata
from collections.abc import Iterable, Sequence

from sentinel_core.plugins import Plugin


def load_plugins(whitelist: Sequence[str]) -> set[Plugin]:
    plugin_entry_points = importlib.metadata.entry_points(group="sentinel.plugins")
    loaded_plugins = {
        entry_point.load()
        for entry_point in plugin_entry_points
        if entry_point.name in whitelist
    }
    print(f"Loaded plugins: {[plugin.name for plugin in loaded_plugins]}")
    return loaded_plugins
