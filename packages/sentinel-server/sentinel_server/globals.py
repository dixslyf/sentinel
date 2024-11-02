import asyncio
import logging
import os

import platformdirs
from nicegui import run

import sentinel_server.config
from sentinel_server.alert import AlertManager, SubscriberManager
from sentinel_server.config import Configuration
from sentinel_server.plugins import PluginManager
from sentinel_server.video import VideoSourceManager

plugin_manager: PluginManager
video_source_manager: VideoSourceManager
alert_manager: AlertManager
subscriber_manager: SubscriberManager

config_path: str
config: Configuration

plugin_manager_loaded: asyncio.Event = asyncio.Event()
plugins_loaded: asyncio.Event = asyncio.Event()

video_source_manager_loaded: asyncio.Event = asyncio.Event()
video_source_manager_loaded_from_db: asyncio.Event = asyncio.Event()

alert_manager_loaded: asyncio.Event = asyncio.Event()
subscriber_manager_loaded: asyncio.Event = asyncio.Event()
subscriber_manager_loaded_from_db: asyncio.Event = asyncio.Event()

config_path_loaded: asyncio.Event = asyncio.Event()
config_loaded: asyncio.Event = asyncio.Event()


def init_plugin_manager() -> None:
    # This should only happen as a programmer error.
    assert config_loaded.is_set()

    global plugin_manager
    plugin_manager = PluginManager(config.plugin_whitelist)
    plugin_manager_loaded.set()


def init_video_source_manager() -> None:
    assert plugin_manager_loaded.is_set()
    assert alert_manager_loaded.is_set()

    global video_source_manager
    global plugin_manager
    global alert_manager
    video_source_manager = VideoSourceManager(plugin_manager, alert_manager)
    video_source_manager.add_task_exception_callback(
        lambda ex: logging.error(f"An error occurred: {ex}")
    )
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


async def init_alert_manager() -> None:
    global alert_manager
    alert_manager = await AlertManager.create()
    alert_manager_loaded.set()


def init_subscriber_manager() -> None:
    assert plugin_manager_loaded.is_set()
    assert alert_manager_loaded.is_set()

    global subscriber_manager
    global plugin_manager
    global alert_manager
    subscriber_manager = SubscriberManager(alert_manager, plugin_manager)
    subscriber_manager_loaded.set()
