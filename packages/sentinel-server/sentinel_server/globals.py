import asyncio
import os
from collections.abc import Collection

import platformdirs
from nicegui import run

import sentinel_server.config
from sentinel_server.config import Configuration
from sentinel_server.plugins import PluginManager
from sentinel_server.video import VideoSourceManager

plugin_manager: PluginManager
video_source_manager: VideoSourceManager

config_path: str
config: Configuration

plugin_manager_loaded: asyncio.Event = asyncio.Event()
plugins_loaded: asyncio.Event = asyncio.Event()

video_source_manager_loaded: asyncio.Event = asyncio.Event()
video_source_manager_loaded_from_db: asyncio.Event = asyncio.Event()

config_path_loaded: asyncio.Event = asyncio.Event()
config_loaded: asyncio.Event = asyncio.Event()


def init_plugin_manager():
    # This should only happen as a programmer error.
    if not config_loaded.is_set():
        raise ValueError("Configuration has not yet been loaded.")

    global plugin_manager
    plugin_manager = PluginManager(config.plugin_whitelist)
    plugin_manager_loaded.set()


def init_video_source_manager():
    global plugin_manager
    global video_source_manager
    video_source_manager = VideoSourceManager(plugin_manager)
    video_source_manager_loaded.set()


async def init_config() -> None:
    global config_path
    global config

    config_path = os.environ.get(
        "SENTINEL_CONFIG_PATH",
        os.path.join(platformdirs.user_config_dir("sentinel"), "config.toml"),
    )
    config_path_loaded.set()

    config = await run.io_bound(sentinel_server.config.get_config, config_path)
    config_loaded.set()
