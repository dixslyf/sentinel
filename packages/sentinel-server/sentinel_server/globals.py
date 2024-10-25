import asyncio
from collections.abc import Collection

from sentinel_server.plugins import PluginManager
from sentinel_server.video import VideoSourceManager

plugin_manager: PluginManager
video_source_manager: VideoSourceManager

plugin_manager_loaded: asyncio.Event = asyncio.Event()
plugins_loaded: asyncio.Event = asyncio.Event()
video_source_manager_loaded: asyncio.Event = asyncio.Event()
video_source_manager_loaded_from_db: asyncio.Event = asyncio.Event()


def init_plugin_manager(plugin_whitelist: Collection[str]):
    global plugin_manager
    plugin_manager = PluginManager(plugin_whitelist)
    plugin_manager_loaded.set()


def init_video_source_manager():
    global plugin_manager
    global video_source_manager
    video_source_manager = VideoSourceManager(plugin_manager)
    video_source_manager_loaded.set()
