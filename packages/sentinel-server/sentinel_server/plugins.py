import importlib.metadata
import logging
from collections.abc import Collection
from dataclasses import dataclass
from importlib.metadata import EntryPoint, EntryPoints
from typing import Callable, Optional

from sentinel_core.plugins import ComponentDescriptor, Plugin

import sentinel_server.globals as globals

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PluginDescriptor:
    name: str
    entry_point: EntryPoint
    plugin: Optional[Plugin] = None


class PluginManager:
    def __init__(self, whitelist: Collection[str]):
        self._whitelist: set[str] = set(whitelist)
        self._plugin_descriptors: Optional[list[PluginDescriptor]] = None
        self._is_dirty: bool = False

    def init_plugins(self) -> None:
        entry_points = self._discover_plugins()

        logger.info(f"Plugin whitelist: {list(self._whitelist)}")
        whitelisted_entry_points = {
            entry_point
            for entry_point in entry_points
            if entry_point.name in self._whitelist
        }

        self._plugin_descriptors = [
            PluginDescriptor(
                entry_point.name,
                entry_point,
                plugin=(
                    self._load_plugin(entry_point)
                    if entry_point in whitelisted_entry_points
                    else None
                ),
            )
            for entry_point in entry_points
        ]

    def add_to_whitelist(self, idx: int) -> None:
        if self._plugin_descriptors is None:
            raise ValueError("Plugins have not been initialised.")

        plugin_desc: PluginDescriptor = self.plugin_descriptors[idx]
        self._whitelist.add(plugin_desc.name)
        logger.info(f'Added plugin "{plugin_desc.name}" to whitelist')

        # Update and save the configuration.
        # TODO: how to make this async?
        globals.config.plugin_whitelist.add(plugin_desc.name)
        globals.config.serialise(globals.config_path)

        self._is_dirty = True

    def remove_from_whitelist(self, idx: int) -> None:
        if self._plugin_descriptors is None:
            raise ValueError("Plugins have not been initialised.")

        plugin_desc: PluginDescriptor = self.plugin_descriptors[idx]
        self._whitelist.remove(plugin_desc.name)
        logger.info(f'Removed plugin "{plugin_desc.name}" from whitelist')

        # Update and save the configuration.
        # TODO: how to make this async?
        globals.config.plugin_whitelist.remove(plugin_desc.name)
        globals.config.serialise(globals.config_path)

        self._is_dirty = True

    def find_plugin_desc(
        self, predicate: Callable[[PluginDescriptor], bool]
    ) -> Optional[PluginDescriptor]:
        return next(
            (
                plugin_desc
                for plugin_desc in self.plugin_descriptors
                if predicate(plugin_desc)
            ),
            None,
        )

    def find_plugin(
        self, predicate: Callable[[Plugin], bool]
    ) -> tuple[Optional[Plugin], Optional[PluginDescriptor]]:
        return next(
            (
                (plugin_desc.plugin, plugin_desc)
                for plugin_desc in self.plugin_descriptors
                if plugin_desc.plugin is not None and predicate(plugin_desc.plugin)
            ),
            (None, None),
        )

    def find_component(
        self, predicate: Callable[[ComponentDescriptor], bool]
    ) -> tuple[Optional[ComponentDescriptor], Optional[PluginDescriptor]]:
        return next(
            (
                (component, plugin_desc)
                for plugin_desc in self.plugin_descriptors
                if plugin_desc.plugin is not None
                for component in plugin_desc.plugin.components
                if predicate(component)
            ),
            (None, None),
        )

    def _discover_plugins(self) -> EntryPoints:
        entry_points = importlib.metadata.entry_points(group="sentinel.plugins")
        logger.info(
            f"Discovered plugins: {[entry_point.name for entry_point in entry_points]}"
        )
        return entry_points

    def _load_plugin(self, entry_point: EntryPoint) -> Plugin:
        plugin = entry_point.load()
        logger.info(f"Loaded plugin: {entry_point.name}")
        return plugin

    @property
    def plugin_descriptors(self) -> list[PluginDescriptor]:
        if self._plugin_descriptors is None:
            raise ValueError("Plugins have not been initialised.")

        return self._plugin_descriptors

    @property
    def is_dirty(self) -> bool:
        return self._is_dirty
