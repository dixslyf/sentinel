import logging
import os

import nicegui
from nicegui import APIRouter, app, run, ui
from nicegui.events import GenericEventArguments

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

    columns = [
        {
            "name": "name",
            "label": "Name",
            "field": "name",
            "required": True,
        },
        {"name": "enabled", "label": "Enabled", "field": "enabled"},
    ]

    def __init__(self) -> None:
        self.table = ui.table(
            columns=PluginTable.columns, rows=[], row_key="name"
        ).props("loading")

        self.dirty_msg = ui.label("Restart Sentinel to apply changes.")

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
        plugins_card = ui.card()
        with plugins_card:
            ui.label("Plugins")
            self.table = PluginTable()

    async def refresh(self) -> None:
        await self.table.refresh()


class AuthenticationSection:
    def __init__(self):
        auth_card = ui.card()
        with auth_card:
            ui.label("Authentication")

            # Username section
            ui.label("Username")
            self.username_input = ui.input(
                label="Username",
                value=app.storage.user["username"],
                validation={"Username cannot be empty": lambda value: len(value) > 0},
            )

            self.username_update_button = ui.button(
                "Update", on_click=self.username_update_button_on_click
            )

            # Password section
            ui.label("Change Password")
            self.password_input = ui.input(
                label="New Password",
                password=True,
                password_toggle_button=True,
                validation={"Password cannot be empty": lambda value: len(value) > 0},
            )

            self.password_confirm_input = ui.input(
                label="Confirm New Password",
                password=True,
                password_toggle_button=True,
                validation={
                    "Passwords do not match": lambda value: value
                    == self.password_input.value
                },
            ).without_auto_validation()

            self.password_update_button = ui.button(
                "Update", on_click=self.password_update_button_on_click
            )

    async def username_update_button_on_click(
        self, button: nicegui.elements.button.Button
    ):
        if not self.username_input.validate():
            return

        user_id = app.storage.user["user_id"]
        await sentinel_server.auth.update_username(user_id, self.username_input.value)
        app.storage.user["username"] = self.username_input.value

        ui.notify("Updated username!")

    async def password_update_button_on_click(
        self, button: nicegui.elements.button.Button
    ):
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
        )

        shutdown_confirm_dialog = ConfirmationDialog(
            "Shut down Sentinel?",
            on_yes=lambda _: app.shutdown(),
        )

        system_card = ui.card()
        with system_card:
            ui.label("System")

            with ui.grid(columns=2):
                ui.button("Restart", on_click=restart_confirm_dialog.open)
                ui.button("Shutdown", on_click=shutdown_confirm_dialog.open)

    def _restart(self, button: nicegui.elements.button.Button) -> None:
        # Log the user out, but don't explicitly redirect to the login page.
        # Once the restart is done, NiceGUI should automatically redirect to the login page.
        app.storage.user.update({"authenticated": False})

        # As suggested by:
        # https://github.com/zauberzeug/nicegui/discussions/1719#discussioncomment-7159050.
        # Assumes `ui.run(..., reload=True)`.
        os.utime(__file__)


@router.page("/settings")
async def settings():
    sentinel_server.ui.pages_shared()
    ui.label("settings")

    plugins_section = PluginsSection()

    AuthenticationSection()

    SystemSection()

    await plugins_section.refresh()
