import logging
from typing import Any

from nicegui import APIRouter, app, run, ui
from nicegui.events import ClickEventArguments, GenericEventArguments

import sentinel_server.auth
import sentinel_server.globals as globals
import sentinel_server.start
from sentinel_server.ui import SharedPageLayout
from sentinel_server.ui.login import logout_user
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
        name = msg.args["row"]["name"]
        enabled = msg.args["row"]["enabled"]

        await globals.plugin_manager_loaded.wait()
        await globals.plugins_loaded.wait()
        plugin_manager = globals.plugin_manager
        if enabled:
            await run.io_bound(plugin_manager.add_to_whitelist, name)
        else:
            await run.io_bound(plugin_manager.remove_from_whitelist, name)

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
    def __init__(self, shared_layout: SharedPageLayout) -> None:
        self._shared_layout: SharedPageLayout = shared_layout

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

        self._shared_layout.refresh()

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

    async def _restart(self, args: ClickEventArguments) -> None:
        await sentinel_server.start.sentinel_setup()
        logout_user()


@router.page("/settings")
async def settings():
    with SharedPageLayout("Settings") as shared_layout:
        AuthenticationSection(shared_layout)
        plugins_section = PluginsSection()
        SystemSection()

    await plugins_section.refresh()
