import logging
import os
from typing import Any

import nicegui
from nicegui import APIRouter, app, run, ui
from nicegui.events import ClickEventArguments, GenericEventArguments

import sentinel_server.auth
import sentinel_server.globals as globals
import sentinel_server.ui
from sentinel_server.ui.utils import ConfirmationDialog

logger = logging.getLogger(__name__)

router = APIRouter()


class PluginTable:
    """
    Represents a table of plugins.
    """

    columns: list[dict[str, Any]] = [
        {
            "name": "name",
            "label": "Name",
            "field": "name",
            "required": True,
        },
        {
            "name": "author",
            "label": "First Author",
            "field": "author",
        },
        {
            "name": "version",
            "label": "Version",
            "field": "version",
        },
        {
            "name": "enabled",
            "label": "Enabled",
            "field": "enabled",
        },
    ]

    def __init__(self) -> None:
        self.dirty_msg = ui.label("Restart Sentinel to apply changes.").classes(
            "text-lg text-[#ff0000] font-semibold"
        )

        self.table = (
            ui.table(columns=PluginTable.columns, rows=[], row_key="name")
            .props("loading")
            .classes("w-7/12 border-2 border-gray-100")
            .props("flat")
            .props("table-header-style='background-color: #f0f0f0'")
        )

        # Enabled checkbox.
        self.table.add_slot(
            "body-cell-enabled",
            '<q-td :props="props">'
            + '<q-checkbox v-model="props.row.enabled" @update:model-value="() => $parent.$emit(\'update_enabled\', props)" />\n'
            + "</q-td>",
        )
        self.table.on("update_enabled", self.update_enabled_handler)

    async def update_enabled_handler(self, msg: GenericEventArguments):
        """
        Handler for when the enabled checkbox for a plugin is toggled.
        """
        # Note: The row index is guaranteed to be the same as the index
        # to the plugin manager's list of plugin descriptors. So, it is
        # safe to pass this index to `add_to_whitelist` and `remove_from_whitelist`.
        row_idx = msg.args["rowIndex"]
        enabled = msg.args["row"]["enabled"]

        await globals.plugin_manager_loaded.wait()
        await globals.plugins_loaded.wait()
        plugin_manager = globals.plugin_manager
        if enabled:
            await run.io_bound(plugin_manager.add_to_whitelist, row_idx)
        else:
            await run.io_bound(plugin_manager.remove_from_whitelist, row_idx)

        await self.refresh_dirty_message()

    async def refresh(self) -> None:
        """
        Refreshes the plugins table by clearing existing rows and
        repopulating it with the list of plugins from the plugin manager.
        """
        self.table.rows.clear()
        self.table.update()

        # Wait for the plugin manager to be initialised.
        await globals.plugin_manager_loaded.wait()
        await globals.plugins_loaded.wait()

        plugin_manager = globals.plugin_manager

        for plugin_desc in plugin_manager.plugin_descriptors:
            self.table.add_row(
                {
                    "name": plugin_desc.name,
                    "author": (
                        # Unfortunately, Python packaging sucks and will only show the first author.
                        plugin_desc.metadata["Author"]
                        if plugin_desc.metadata is not None
                        else "Unknown"
                    ),
                    "version": (
                        plugin_desc.metadata["Version"]
                        if plugin_desc.metadata is not None
                        else "Unknown"
                    ),
                    "enabled": plugin_desc.plugin is not None,
                }
            )

        self.table.props("loading=false")
        logger.debug("Refreshed plugin table")

        await self.refresh_dirty_message()

    async def refresh_dirty_message(self) -> None:
        await globals.plugin_manager_loaded.wait()
        await globals.plugins_loaded.wait()
        plugin_manager = globals.plugin_manager
        self.dirty_msg.visible = plugin_manager.is_dirty


class PluginsSection:
    def __init__(self):
        plugins_card = (
            ui.card().props("flat").classes("w-full border-b-2 border-gray-100")
        )
        with plugins_card:
            ui.label("Available Plugins").classes("text-3xl font-bold text-[#4a4e69]")
            with ui.element("div").classes("w-full flex flex-col items-center"):
                self.table = PluginTable()

    async def refresh(self) -> None:
        await self.table.refresh()


class AuthenticationSection:
    def __init__(self) -> None:
        auth_card = ui.card().classes("w-full border-b-2 border-gray-100").props("flat")
        with auth_card:
            ui.label("User Authentication").classes("text-3xl font-bold text-[#4a4e69]")

            with ui.element("div").classes("w-full flex justify-between"):
                # Username section
                with ui.element("div").classes("w-2/6"):

                    ui.label("Username").classes("text-xl font-semibold text-[#4a4e69]")
                    self.username_input = ui.input(
                        label="Username",
                        value=app.storage.user["username"],
                        validation={
                            "Username cannot be empty": lambda value: len(value) > 0
                        },
                    ).classes("w-full text-[#4a4e69]")

                    with ui.element("div").classes("w-full flex justify-end"):
                        self.username_update_button = (
                            ui.button(
                                "Update", on_click=self.username_update_button_on_click
                            )
                            .classes(
                                "text-md text-[#cad3f5] bg-black rounded-xl hover:bg-gray-500"
                            )
                            .props("no-caps")
                        )

                # Password section
                with ui.element("div").classes("mr-40 w-2/6"):

                    ui.label("Change Password").classes(
                        "text-xl font-semibold text-[#4a4e69]"
                    )
                    self.password_input = ui.input(
                        label="New Password",
                        password=True,
                        password_toggle_button=True,
                        validation={
                            "Password cannot be empty": lambda value: len(value) > 0
                        },
                    ).classes("w-full text-[#4a4e69]")

                    self.password_confirm_input = (
                        ui.input(
                            label="Confirm New Password",
                            password=True,
                            password_toggle_button=True,
                            validation={
                                "Passwords do not match": lambda value: value
                                == self.password_input.value
                            },
                        )
                        .without_auto_validation()
                        .classes("w-full text-[#4a4e69]")
                    )

                    with ui.element("div").classes("w-full flex justify-end"):
                        self.password_update_button = (
                            ui.button(
                                "Update", on_click=self.password_update_button_on_click
                            )
                            .classes(
                                "text-md text-[#cad3f5] bg-black rounded-xl hover:bg-gray-500"
                            )
                            .props("no-caps")
                        )

    async def username_update_button_on_click(self, args: ClickEventArguments) -> None:
        if not self.username_input.validate():
            return

        user_id = app.storage.user["user_id"]
        await sentinel_server.auth.update_username(user_id, self.username_input.value)
        app.storage.user["username"] = self.username_input.value

        ui.notify("Updated username!")

    async def password_update_button_on_click(self, args: ClickEventArguments) -> None:
        if (
            not self.password_input.validate()
            or not self.password_confirm_input.validate()
        ):
            return

        user_id = app.storage.user["user_id"]
        await sentinel_server.auth.update_password(user_id, self.password_input.value)

        ui.notify("Updated password!")


class SystemSection:
    def __init__(self) -> None:
        restart_confirm_dialog = ConfirmationDialog(
            "Restart Sentinel?",
            on_yes=self._restart,
            background=False,
        )

        shutdown_confirm_dialog = ConfirmationDialog(
            "Shut down Sentinel?",
            on_yes=lambda _: app.shutdown(),
            background=False,
        )

        system_card = ui.card().props("flat")
        with system_card:
            ui.label("System Controls").classes("text-3xl font-bold text-[#4a4e69]")

            with ui.grid(columns=2):
                ui.button("Restart", on_click=restart_confirm_dialog.open).classes(
                    "text-md text-[#cad3f5] bg-black rounded-xl hover:bg-gray-500"
                ).props("no-caps")
                ui.button("Shutdown", on_click=shutdown_confirm_dialog.open).classes(
                    "text-md text-[#cad3f5] bg-black rounded-xl hover:bg-gray-500"
                ).props("no-caps")

    def _restart(self, args: ClickEventArguments) -> None:
        # Log the user out, but don't explicitly redirect to the login page.
        # Once the restart is done, NiceGUI should automatically redirect to the login page.
        app.storage.user.update({"authenticated": False})

        # As suggested by:
        # https://github.com/zauberzeug/nicegui/discussions/1719#discussioncomment-7159050.
        # Assumes `ui.run(..., reload=True)`.
        os.utime(__file__)


@router.page("/settings")
async def settings():
    sentinel_server.ui.add_global_style()
    sentinel_server.ui.pages_shared()

    with ui.element("div").classes("flex flex-col w-full gap-5"):
        ui.label("Settings").classes("px-5 py-2 text-4xl font-bold text-[#4a4e69] border-b-2 border-gray-200")
        AuthenticationSection()
        plugins_section = PluginsSection()
        SystemSection()

    await plugins_section.refresh()
