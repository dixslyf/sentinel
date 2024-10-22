import logging
import os
import secrets
import sys
from typing import Optional

import platformdirs
from fastapi import Request
from fastapi.responses import RedirectResponse
from nicegui import app, run, ui
from starlette.middleware.base import BaseHTTPMiddleware
from tortoise import Tortoise

import sentinel_server.auth
import sentinel_server.config
from sentinel_server.plugins import discover_plugins, load_plugins

UNRESTRICTED_PAGE_ROUTES: set[str] = {"/", "/login"}


async def setup():
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
        db_url=config.db_url, modules={"models": ["sentinel_server.auth"]}
    )
    await Tortoise.generate_schemas(safe=True)

    # Create the default user if it does not exist.
    await sentinel_server.auth.ensure_default_user()

    # Discover and load plugins.
    plugins = load_plugins(discover_plugins(), config.plugin_whitelist)

    logging.info("Sentinel started")


async def shutdown():
    await Tortoise.close_connections()
    logging.info("Sentinel shutdown")


@ui.page("/")
def index():
    return RedirectResponse("/login")


@ui.page("/login")
def login() -> Optional[RedirectResponse]:
    if app.storage.user.get("authenticated", False):
        return RedirectResponse("/dashboard")

    with ui.card().classes("absolute-center"):
        username_input = ui.input("Username")
        password_input = ui.input(
            "Password", password=True, password_toggle_button=True
        )

    async def try_login() -> None:
        logging.info(f"Checking login credentials for: {username_input.value}")

        user: sentinel_server.auth.User = await sentinel_server.auth.User.get_or_none(
            username=username_input.value
        )

        if not user or not user.verify_password(password_input.value):
            logging.info(f"Authentication failed for: {username_input.value}")
            ui.notify("Wrong username or password", color="negative")
            return None

        app.storage.user.update(
            {"username": username_input.value, "authenticated": True}
        )
        ui.navigate.to(app.storage.user.get("referrer_path", "/"))

    username_input.on("keydown.enter", try_login)
    password_input.on("keydown.enter", try_login)
    ui.button("Log in", on_click=try_login)

    return None


def pages_shared():
    with ui.left_drawer(fixed=False).classes("shadow-2xl") as left_drawer:
        ui.button("Dashboard", on_click=lambda: ui.navigate.to("/dashboard"))
        ui.button("Cameras", on_click=lambda: ui.navigate.to("/cameras"))
        ui.button("Devices", on_click=lambda: ui.navigate.to("/devices"))
        ui.button("Alerts", on_click=lambda: ui.navigate.to("/alerts"))
        ui.button("Settings", on_click=lambda: ui.navigate.to("/settings"))

    with ui.header():
        ui.button(on_click=lambda: left_drawer.toggle(), icon="menu")
        ui.label("Sentinel")


@ui.page("/dashboard")
def dashboard():
    ui.label("dashboard")
    pages_shared()


@ui.page("/cameras")
def cameras():
    ui.label("cameras")
    pages_shared()


@ui.page("/devices")
def devices():
    ui.label("devices")
    pages_shared()


@ui.page("/alerts")
def alerts():
    ui.label("alerts")
    pages_shared()


@ui.page("/settings")
def settings():
    ui.label("settings")
    pages_shared()


class AuthenticationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not app.storage.user.get("authenticated", False):
            if (
                not request.url.path.startswith("/_nicegui")
                and request.url.path not in UNRESTRICTED_PAGE_ROUTES
            ):
                app.storage.user["referrer_path"] = request.url.path
                return RedirectResponse("/login")
        return await call_next(request)


def entry() -> None:
    app.add_middleware(AuthenticationMiddleware)
    app.on_startup(setup)
    app.on_shutdown(shutdown)
    ui.run(title="Sentinel", storage_secret=secrets.token_urlsafe(nbytes=256))


if __name__ in {"__main__", "__mp_main__"}:
    entry()
