import logging
from typing import Any

from nicegui import APIRouter, ui
from nicegui.elements.input import Input
from nicegui.elements.select import Select
from nicegui.events import GenericEventArguments, ValueChangeEventArguments

import sentinel_server.globals
import sentinel_server.tasks
import sentinel_server.ui

logger = logging.getLogger(__name__)

router = APIRouter()


class DeviceTable:
    """
    Represents a table of devices subscribed to alerts.

    The table is dynamically populated with devices retrieved from the database.
    """

    columns: list[dict[str, Any]] = [
        {
            "name": "id",
            "label": "ID",
            "field": "id",
            "required": True,
            "align": "middle",
        },
        {"name": "name", "label": "Name", "field": "name"},
        {
            "name": "plugin_component",
            "label": "Plugin / Component",
            "field": "plugin_component",
        },
        {"name": "enabled", "label": "Enabled", "field": "enabled"},
    ]

    def __init__(self) -> None:
        self.table = ui.table(columns=DeviceTable.columns, rows=[], row_key="id").props(
            "loading"
        )

        # Enabled checkbox.
        self.table.add_slot(
            "body-cell-enabled",
            '<q-td :props="props">'
            + '<q-checkbox v-model="props.row.enabled" @update:model-value="() => $parent.$emit(\'update_enabled\', props.row)" />\n'
            + "</q-td>",
        )
        self.table.on("update_enabled", self.update_enabled_handler)

    async def update_enabled_handler(self, msg: GenericEventArguments):
        """
        Handler for when the enabled checkbox for a device is toggled.
        """
        id = msg.args["id"]
        enabled = msg.args["enabled"]

        # FIXME: remove these placeholders
        if enabled:
            ui.notify(f"Enabled {id}")
        else:
            ui.notify(f"Disabled {id}")

    async def refresh(self) -> None:
        """
        Refreshes the devices table by clearing existing rows and
        repopulating it with camera source data from the database.
        """
        # FIXME: remove this and modify the code below
        # when the subscriber manager has been implemented
        self.table.props("loading=false")
        logger.debug("Refreshed devices table")
        return

        self.table.rows.clear()
        self.table.update()

        subscribers: dict[int, Any] = {}
        for _, sub in subscribers.items():
            self.table.add_row(
                {
                    "id": sub.id,
                    "name": sub.name,
                    "plugin_component": f"{sub.plugin_name} / {sub.component_name}",
                    "enabled": sub.enabled,
                }
            )

        self.table.props("loading=false")
        logger.debug("Refreshed devices table")


class AddDeviceDialog:
    """
    Represents a dialog for adding new subscribers.

    Input fields are dynamically created and rendered based on the selected subscriber plugin and component,
    allowing the user to enter custom configuration for the subscriber.
    """

    def __init__(self, device_table: DeviceTable) -> None:
        """
        Initialises the dialog with the given device table reference.

        The device table reference is needed to refresh the table when the user has finished
        entering data for a subscriber.

        Args:
            device_table (DeviceTable): The device table instance to refresh after adding a new subscriber.
        """
        self.device_table = device_table

        self.dialog = ui.dialog()

        # Dictionary that maps each argument display name of the currently selected
        # plugin component to a NiceGUI input or select box. Used for retrieving the user's
        # inputs when they complete the form.
        self.component_inputs: dict[str, Input | Select] = {}

        with self.dialog, ui.card():
            ui.label("Add Device")

            # Name of the device.
            self.name_input = ui.input(label="Name")

            # Selection box for the plugin component.
            self.component_select = ui.select({}, label="Device type")

            # Section containing inputs for configuration specific
            # to the plugin component.
            self.component_section = ui.element("div")

            # Update the form to show configuration inputs for
            # the currently selected plugin component.
            self.component_select.on_value_change(self._update_component_config_inputs)

            with ui.grid(columns=2):
                ui.button("Close", on_click=self.close)
                ui.button("Finish", on_click=self._on_finish)

    async def open(self):
        """Opens the dialog."""
        await self._update_plugin_component_select_options()
        self.dialog.open()

    def close(self):
        """Closes the dialog."""
        self.dialog.close()

    async def _update_plugin_component_select_options(self) -> None:
        """Updates the options for the dropdown selection box for the video stream component."""
        # FIXME: update this once a subscriber manager has been implemented
        pass

    def _update_component_config_inputs(self, args: ValueChangeEventArguments) -> None:
        """
        Updates the user interface by dynamically adding input fields
        for the currently selected plugin component's configuration.
        """
        self.component_inputs = {}
        self.component_section.clear()

        comp = self.component_select.value
        with self.component_section:
            for arg in comp.args:
                if arg.choices is None:
                    input = ui.input(label=arg.display_name)
                    self.component_inputs[arg.arg_name] = input
                else:
                    select = ui.select(
                        {choice.value: choice.display_name for choice in arg.choices},
                        label=arg.display_name,
                    )
                    self.component_inputs[arg.arg_name] = select

    async def _on_finish(self) -> None:
        """
        Completes the subscriber addition process by creating a new subscriber in the database,
        refreshing the table and closing the dialog.
        """
        # Keyword args for creating the subscriber.
        subscriber_kwargs = {
            arg_name: input.value for arg_name, input in self.component_inputs.items()
        }

        comp = self.component_select.value

        try:
            # FIXME: make an API call to the subscriber manager
            pass
        except Exception as ex:
            ui.notify(f"An error occurred: {ex}", color="negative")

        await self.device_table.refresh()
        self.close()


@router.page("/devices")
async def devices_page() -> None:
    sentinel_server.ui.add_global_style()
    sentinel_server.ui.pages_shared()

    ui.label("Devices")

    table = DeviceTable()
    dialog = AddDeviceDialog(table)

    with ui.row():
        ui.button("Add", on_click=dialog.open)

    # Wait for the page to load before refreshing the table.
    await ui.context.client.connected()
    await table.refresh()
