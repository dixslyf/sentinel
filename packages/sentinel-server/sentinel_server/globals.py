import asyncio
import logging
import os

import platformdirs
from nicegui import run

import sentinel_server.config
from sentinel_server.alert import AlertManager, SubscriberManager, SubscriptionRegistrar
from sentinel_server.config import Configuration
from sentinel_server.plugins import PluginManager
from sentinel_server.video import VideoSourceManager

plugin_manager: PluginManager
video_source_manager: VideoSourceManager
subscription_registrar: SubscriptionRegistrar
subscriber_manager: SubscriberManager
alert_manager: AlertManager

config_path: str
config: Configuration

plugin_manager_loaded: asyncio.Event = asyncio.Event()
plugins_loaded: asyncio.Event = asyncio.Event()

video_source_manager_loaded: asyncio.Event = asyncio.Event()
video_source_manager_loaded_from_db: asyncio.Event = asyncio.Event()

subscription_registrar_loaded: asyncio.Event = asyncio.Event()
subscriber_manager_loaded: asyncio.Event = asyncio.Event()
subscriber_manager_loaded_from_db: asyncio.Event = asyncio.Event()
alert_manager_loaded: asyncio.Event = asyncio.Event()

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
    assert subscription_registrar_loaded.is_set()

    global video_source_manager
    global plugin_manager
    global subscription_registrar
    video_source_manager = VideoSourceManager(plugin_manager, subscription_registrar)
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
    assert subscription_registrar_loaded.is_set()

    global alert_manager
    global subscription_registrar

    alert_manager = await AlertManager.create(subscription_registrar)
    alert_manager_loaded.set()


def init_subscription_registrar() -> None:
    global subscription_registrar
    subscription_registrar = SubscriptionRegistrar()
    subscription_registrar_loaded.set()


def init_subscriber_manager() -> None:
    assert plugin_manager_loaded.is_set()
    assert subscription_registrar_loaded.is_set()

    global subscriber_manager
    global plugin_manager
    global subscription_registrar
    subscriber_manager = SubscriberManager(subscription_registrar, plugin_manager)
    subscriber_manager_loaded.set()
