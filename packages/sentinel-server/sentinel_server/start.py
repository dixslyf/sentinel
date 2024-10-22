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
from sentinel_server.plugins import ComponentKind, PluginManager

UNRESTRICTED_PAGE_ROUTES: set[str] = {"/", "/login"}

plugin_manager: PluginManager


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
    global plugin_manager
    plugin_manager = PluginManager(config.plugin_whitelist)
    await run.io_bound(plugin_manager.discover_plugins)
    await run.io_bound(plugin_manager.load_plugins)

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
        login_button = ui.button("Log in")

    async def try_login() -> None:
        logging.info(f"Checking login credentials for: {username_input.value}")

        user: sentinel_server.auth.User = await sentinel_server.auth.User.get_or_none(
            username=username_input.value
        )

        if not user or not user.verify_password(password_input.value):
            logging.info(f"Authentication failed for: {username_input.value}")
            ui.notify("Wrong username or password", color="negative")
            return None

        logging.info(f"Authentication succeeded for: {username_input.value}")
        app.storage.user.update(
            {"username": username_input.value, "authenticated": True}
        )
        ui.navigate.to(app.storage.user.get("referrer_path", "/"))

    username_input.on("keydown.enter", try_login)
    password_input.on("keydown.enter", try_login)
    login_button.on_click(try_login)

    return None


def pages_shared():
    # TODO: How to make the drawer retain its open/closed state across pages?
    with ui.left_drawer(fixed=False, value=False).classes("shadow-2xl") as left_drawer:
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
def cameras() -> None:
    pages_shared()

    ui.label("Cameras")
    columns = [
        {
            "name": "id",
            "label": "ID",
            "field": "id",
            "required": True,
            "align": "middle",
        },
        {"name": "name", "label": "Name", "field": "name"},
        {"name": "status", "label": "Status", "field": "status"},
    ]

    rows = [
        {"id": "1", "name": "Example camera", "status": "online"},
    ]

    ui.table(columns=columns, rows=rows, row_key="id")

    global plugin_manager
    vidstream_comps = {
        component.display_name: component
        for component in plugin_manager.components(ComponentKind.VideoStream)
    }
    detector_comps = {
        component.display_name: component
        for component in plugin_manager.components(ComponentKind.Detector)
    }

    # Dialog for adding a new video stream.
    # TODO: WIP
    with ui.dialog() as dialog, ui.card():
        with ui.grid(columns=2):
            ui.label("Name")
            name_input = ui.input()

            # Video stream options.
            ui.label("Video Stream Plugin:")
            vidstream_select = ui.select([comp_name for comp_name in vidstream_comps])
            vidstream_section = ui.card_section().classes("col-span-2")
            vidstream_inputs: dict

            def show_vidstream_options(el):
                nonlocal vidstream_inputs
                vidstream_inputs = {}
                vidstream_section.clear()
                with vidstream_section, ui.grid(columns=2):
                    for arg in vidstream_comps[el.value].args:
                        ui.label(arg.display_name)
                        input = ui.input()
                        vidstream_inputs[arg.arg_name] = input

            vidstream_select.on_value_change(show_vidstream_options)

            # Detector options.
            ui.label("Detector Plugin:")
            detector_select = ui.select([comp_name for comp_name in detector_comps])
            detector_section = ui.card_section().classes("col-span-2")

            def show_detector_options(el):
                detector_section.clear()
                with detector_section:
                    ui.label(el.value)

            detector_select.on_value_change(show_detector_options)

            ui.button("Close", on_click=dialog.close)

            def on_finish():
                vidstream_kwargs = {
                    arg_name: input.value
                    for arg_name, input in vidstream_inputs.items()
                }

                vidstream_cls = vidstream_comps[vidstream_select.value].cls
                try:
                    vidstream = vidstream_cls(**vidstream_kwargs)
                    logging.info(vidstream)
                    dialog.close()
                except Exception as ex:
                    ui.notify(f"An error occurred: {ex.message()}", color="negative")

            ui.button("Finish", on_click=on_finish)

    with ui.row():
        ui.button("Add", on_click=lambda: dialog.open())


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
