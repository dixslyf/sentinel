import importlib.metadata
import logging
from collections.abc import Collection, Iterable
from dataclasses import dataclass
from importlib.metadata import EntryPoint, EntryPoints
from typing import Optional

from sentinel_core.plugins import Plugin

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PluginDescriptor:
    name: str
    entry_point: EntryPoint
    plugin: Plugin


class PluginManager:
    def __init__(self, whitelist: Collection[str]):
        self._whitelist: set[str] = set(whitelist)
        self._plugin_descriptors: Optional[set[PluginDescriptor]] = None

    def init_plugins(self) -> None:
        entry_points = self._discover_plugins()
        whitelisted_entry_points = {
            entry_point
            for entry_point in entry_points
            if entry_point.name in self._whitelist
        }

        self._plugin_descriptors = {
            PluginDescriptor(entry_point.name, entry_point, plugin)
            for entry_point, plugin in self._load_plugins(
                whitelisted_entry_points
            ).items()
        }

    def _discover_plugins(self) -> EntryPoints:
        entry_points = importlib.metadata.entry_points(group="sentinel.plugins")
        logger.info(
            f"Discovered plugins: {[entry_point.name for entry_point in entry_points]}"
        )
        return entry_points

    def _load_plugins(
        self, entry_points: Iterable[EntryPoint]
    ) -> dict[EntryPoint, Plugin]:
        loaded_plugins = {
            entry_point: entry_point.load() for entry_point in entry_points
        }

        logger.info(f"Plugin whitelist: {list(self._whitelist)}")
        logger.info(
            f"Loaded plugins: {[entry_point.name for entry_point in entry_points]}"
        )

        return loaded_plugins

    @property
    def plugin_descriptors(self) -> Optional[set[PluginDescriptor]]:
        return self._plugin_descriptors
