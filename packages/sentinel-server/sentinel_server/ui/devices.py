import logging
from typing import Any

from nicegui import APIRouter, ui
from nicegui.elements.input import Input
from nicegui.elements.select import Select
from nicegui.events import GenericEventArguments, ValueChangeEventArguments

import sentinel_server.globals as globals
import sentinel_server.tasks
import sentinel_server.ui
from sentinel_server.alert import ManagedSubscriber, SubscriberStatus

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
            "align": "left",
        },
        {"name": "name", "label": "Name", "field": "name"},
        {
            "name": "plugin_component",
            "label": "Plugin / Component",
            "field": "plugin_component",
        },
        {"name": "status", "label": "Status", "field": "status"},
        {"name": "enabled", "label": "Enabled", "field": "enabled"},
    ]

    def __init__(self) -> None:
        self.table = (
            ui.table(columns=DeviceTable.columns, rows=[], row_key="id")
            .props("loading")
            .classes("w-11/12 border-2 border-gray-100")
            .props("table-header-style='background-color: #f0f0f0'")
            .props("flat")
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

        row = next((r for r in self.table.rows if r["id"] == id), None)
        assert row is not None

        await globals.subscriber_manager_loaded.wait()
        await globals.subscriber_manager_loaded_from_db.wait()
        subscriber_manager = globals.subscriber_manager

        if enabled:
            await subscriber_manager.enable_subscriber(id)
            row["enabled"] = True
        else:
            await subscriber_manager.disable_subscriber(id)
            row["enabled"] = False

        self.table.update()

    async def refresh(self) -> None:
        """
        Refreshes the devices table by clearing existing rows and
        repopulating it with camera source data from the database.
        """
        await globals.subscriber_manager_loaded.wait()
        await globals.subscriber_manager_loaded_from_db.wait()

        self.table.rows.clear()

        managed_subscribers: dict[int, ManagedSubscriber] = (
            globals.subscriber_manager.managed_subscribers
        )

        for _, sub in managed_subscribers.items():
            self.table.add_row(
                {
                    "id": sub.id,
                    "name": sub.name,
                    "plugin_component": f"{sub.plugin_name} / {sub.component_name}",
                    "status": "OK" if sub.status == SubscriberStatus.Ok else "Error",
                    "enabled": sub.enabled,
                }
            )

        self.table.props("loading=false")
        self.table.update()
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

        with self.dialog, ui.card().classes("w-1/5"):
            with ui.element("div").classes("w-full flex justify-between"):
                ui.label("Add Device").classes("flex items-center text-xl bold")
                # close button
                with ui.button(on_click=self.close).props("flat").classes("w-10"):
                    ui.icon("close").classes("text-gray-400")

            # Name of the device.
            self.name_input = ui.input(label="Name").classes("w-full")

            # Selection box for the plugin component.
            self.component_select = ui.select({}, label="Device type").classes("w-full")

            # Section containing inputs for configuration specific
            # to the plugin component.
            self.component_section = ui.element("div").classes("w-full")

            # Update the form to show configuration inputs for
            # the currently selected plugin component.
            self.component_select.on_value_change(self._update_component_config_inputs)

            with ui.element("div").classes("w-full flex justify-end"):
                ui.button("Finish", on_click=self._on_finish).classes(
                    "text-white bg-black"
                )

    async def open(self):
        """
        Opens the dialog, or if no subscriber components are available,
        shows a notification to the user to prompt them to install and enable plugins.
        """
        if not await self._check_select_options():
            ui.notify(
                "No subscriber plugins enabled. "
                "Plugins can be managed from the Settings page."
            )
            return

        await self._update_plugin_component_select_options()
        self.dialog.open()

    def close(self):
        """Closes the dialog."""
        self.dialog.close()

    async def _check_select_options(self) -> bool:
        await globals.subscriber_manager_loaded.wait()
        return len(globals.subscriber_manager.available_subscriber_components()) > 0

    async def _update_plugin_component_select_options(self) -> None:
        """Updates the options for the dropdown selection box for the component."""
        await globals.subscriber_manager_loaded.wait()
        available_subscriber_components = (
            globals.subscriber_manager.available_subscriber_components()
        )

        self.component_select.set_options(
            {comp: comp.display_name for comp in available_subscriber_components}
        )

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

        try:
            await globals.subscriber_manager_loaded.wait()
            await globals.subscriber_manager.add_subscriber(
                name=self.name_input.value,
                component=self.component_select.value,
                config=subscriber_kwargs,
            )
        except Exception as ex:
            ui.notify(f"An error occurred: {ex}", color="negative")

        await self.device_table.refresh()
        self.close()


@router.page("/devices")
async def devices_page() -> None:
    sentinel_server.ui.add_global_style()
    sentinel_server.ui.pages_shared()

    # ui.label("Devices")
    with ui.element("div").classes(
        "w-full flex flex-col gap-5 justify-center text-center mt-10"
    ):

        with ui.element("div").classes("flex justify-center text-center"):
            table = DeviceTable()
            dialog = AddDeviceDialog(table)

        with ui.element("div").classes("w-full flex justify-center"):
            with ui.element("div").classes("w-11/12 flex justify-end"):
                ui.button("Add", on_click=dialog.open).classes(
                    "bg-black rounded-xl py-1 px-3 text-[#cad3f5]"
                ).props("no-caps")

    # Wait for the page to load before refreshing the table.
    await ui.context.client.connected()
    await table.refresh()
