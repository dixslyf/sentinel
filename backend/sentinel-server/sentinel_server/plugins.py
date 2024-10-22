import importlib.metadata
import logging
from collections.abc import Collection
from importlib.metadata import EntryPoints
from typing import Iterable, Optional

from sentinel_core.plugins import ComponentDescriptor, ComponentKind, Plugin
from sentinel_core.video import VideoStream

logger = logging.getLogger(__name__)


class PluginManager:
    def __init__(self, whitelist: Collection[str]):
        self._whitelist = set(whitelist)
        self._entry_points: Optional[EntryPoints] = None
        self._plugins: Optional[set[Plugin]] = None

    def discover_plugins(self):
        entry_points = importlib.metadata.entry_points(group="sentinel.plugins")
        logger.info(
            f"Discovered plugins: {[entry_point.name for entry_point in entry_points]}"
        )
        self._entry_points = entry_points

    def load_plugins(self):
        if self._entry_points == None:
            raise ValueError("Plugins have not been discovered.")

        loaded_plugins = {
            (entry_point, entry_point.load())
            for entry_point in self._entry_points
            if entry_point.name in self._whitelist
        }
        self._plugins = loaded_plugins
        logger.info(f"Plugin whitelist: {list(self._whitelist)}")
        logger.info(
            f"Loaded plugins: {[entry_point.name for (entry_point, _) in loaded_plugins]}"
        )

        logger.debug(f"Components available: {list(self.components())}")

    def components(
        self, kind: Optional[ComponentKind] = None
    ) -> Iterable[ComponentDescriptor[VideoStream]]:
        if self._plugins is None:
            raise ValueError("Plugins have not been loaded.")

        gen = (
            component for _, plugin in self._plugins for component in plugin.components
        )

        if kind is None:
            return gen
        else:
            return (component for component in gen if component.kind is kind)
