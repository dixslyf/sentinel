import logging
import os
import secrets
import sys

import platformdirs
from fastapi.responses import RedirectResponse
from nicegui import app, run, ui
from tortoise import Tortoise

import sentinel_server.auth
import sentinel_server.config
import sentinel_server.globals
import sentinel_server.ui.alerts
import sentinel_server.ui.cameras
import sentinel_server.ui.dashboard
import sentinel_server.ui.devices
import sentinel_server.ui.login
import sentinel_server.ui.settings


async def setup():
    # Set up routers.
    app.include_router(sentinel_server.ui.login.router)
    app.include_router(sentinel_server.ui.alerts.router)
    app.include_router(sentinel_server.ui.cameras.router)
    app.include_router(sentinel_server.ui.dashboard.router)
    app.include_router(sentinel_server.ui.devices.router)
    app.include_router(sentinel_server.ui.settings.router)

    # Configure logging.
    log_level = os.environ.get("SENTINEL_LOG_LEVEL", "INFO").upper()
    if log_level not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
        log_level = "NOTSET"

    logging.basicConfig(
        stream=sys.stdout,
        level=getattr(logging, log_level),
        format="[%(levelname)s][%(asctime)s] %(message)s",
    )

    # Create configuration and data directories.
    await run.io_bound(
        os.makedirs, platformdirs.user_config_dir("sentinel"), exist_ok=True
    )
    await run.io_bound(
        os.makedirs, platformdirs.user_data_dir("sentinel"), exist_ok=True
    )

    # Load configuration from the configuration file.
    config_path = os.environ.get(
        "SENTINEL_CONFIG_PATH",
        os.path.join(platformdirs.user_config_dir("sentinel"), "config.toml"),
    )
    config = await run.io_bound(sentinel_server.config.get_config, config_path)

    # Initialise database.
    await Tortoise.init(
        db_url=config.db_url,
        modules={"models": ["sentinel_server.models"]},
    )
    await Tortoise.generate_schemas(safe=True)

    # Create the default user if it does not exist.
    await sentinel_server.auth.ensure_default_user()

    # Discover and load plugins.
    sentinel_server.globals.init_plugin_manager(config.plugin_whitelist)
    await run.io_bound(sentinel_server.globals.plugin_manager.init_plugins)

    sentinel_server.globals.init_video_source_manager()
    await sentinel_server.globals.video_source_manager.load_video_sources_from_db()

    logging.info("Sentinel started")


async def shutdown():
    await Tortoise.close_connections()
    logging.info("Sentinel shutdown")


@ui.page("/")
def index():
    return RedirectResponse("/login")


def entry() -> None:
    app.add_middleware(sentinel_server.ui.login.AuthenticationMiddleware)
    app.on_startup(setup)
    app.on_shutdown(shutdown)
    ui.run(
        title="Sentinel", storage_secret=secrets.token_urlsafe(nbytes=256), reload=True
    )


if __name__ in {"__main__", "__mp_main__"}:
    entry()
