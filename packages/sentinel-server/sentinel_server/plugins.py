import importlib.metadata
import logging
from collections.abc import Collection
from dataclasses import dataclass
from importlib.metadata import (
    EntryPoint,
    EntryPoints,
    PackageMetadata,
    PackageNotFoundError,
)
from typing import Callable, Optional

from sentinel_core.plugins import ComponentDescriptor, Plugin

from sentinel_server.config import Configuration

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PluginDescriptor:
    name: str
    entry_point: EntryPoint
    metadata: Optional[PackageMetadata] = None
    plugin: Optional[Plugin] = None


class PluginManager:
    def __init__(
        self, whitelist: Collection[str], config: Configuration, config_path: str
    ):
        self.config: Configuration = config
        self.config_path: str = config_path

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
                PluginManager._get_metadata(entry_point),
                plugin=(
                    self._load_plugin(entry_point)
                    if entry_point in whitelisted_entry_points
                    else None
                ),
            )
            for entry_point in entry_points
        ]

    def add_to_whitelist(self, name: str) -> bool:
        if name in self._whitelist:
            return False

        self._whitelist.add(name)
        logger.info(f'Added plugin "{name}" to whitelist')

        # Update and save the configuration.
        self.config.plugin_whitelist.add(name)
        self.config.serialise(self.config_path)

        self._is_dirty = True
        return True

    def remove_from_whitelist(self, name: str) -> bool:
        if name not in self._whitelist:
            return False

        self._whitelist.remove(name)
        logger.info(f'Removed plugin "{name}" from whitelist')

        # Update and save the configuration.
        self.config.plugin_whitelist.remove(name)

        self.config.serialise(self.config_path)

        self._is_dirty = True

        return True

    def get_whitelist(self) -> Collection[str]:
        return self._whitelist

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

    @staticmethod
    def _get_metadata(entry_point: EntryPoint) -> Optional[PackageMetadata]:
        dist_name = (
            entry_point.dist.name if entry_point.dist is not None else entry_point.name
        )
        try:
            return importlib.metadata.metadata(dist_name)
        except PackageNotFoundError:
            return None
