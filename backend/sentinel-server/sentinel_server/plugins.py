import importlib.metadata
import logging
from collections.abc import Collection
from importlib.metadata import EntryPoints

from sentinel_core.plugins import Plugin

logger = logging.getLogger(__name__)


def discover_plugins() -> EntryPoints:
    entry_points = importlib.metadata.entry_points(group="sentinel.plugins")
    logger.info(
        f"Discovered plugins: {[entry_point.name for entry_point in entry_points]}"
    )
    return entry_points


def load_plugins(
    plugin_entry_points: EntryPoints, whitelist: Collection[str]
) -> set[Plugin]:
    loaded_plugins = {
        entry_point.load()
        for entry_point in plugin_entry_points
        if entry_point.name in whitelist
    }
    logger.info(f"Loaded plugins: {[plugin.name for plugin in loaded_plugins]}")
    return loaded_plugins
