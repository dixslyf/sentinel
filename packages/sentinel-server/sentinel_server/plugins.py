import importlib.metadata
from collections.abc import Iterable

from sentinel_core.plugins import Plugin


def load_plugins() -> Iterable[Plugin]:
    plugin_entry_points = importlib.metadata.entry_points(group="sentinel.plugins")
    return [entry_point.load() for entry_point in plugin_entry_points]
