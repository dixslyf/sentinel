from collections.abc import Collection

from sentinel_server.plugins import PluginManager
from sentinel_server.video import VideoSourceManager

plugin_manager: PluginManager
video_source_manager: VideoSourceManager


def init_plugin_manager(plugin_whitelist: Collection[str]):
    global plugin_manager
    plugin_manager = PluginManager(plugin_whitelist)


def init_video_source_manager():
    global plugin_manager
    global video_source_manager
    video_source_manager = VideoSourceManager(plugin_manager)
