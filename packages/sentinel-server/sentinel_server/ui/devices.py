import logging
from typing import Any

from nicegui import APIRouter, ui
from nicegui.events import GenericEventArguments

import sentinel_server.globals
import sentinel_server.tasks
import sentinel_server.ui

logger = logging.getLogger(__name__)

router = APIRouter()


class DevicesTable:
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
        self.table = ui.table(
            columns=DevicesTable.columns, rows=[], row_key="id"
        ).props("loading")

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


@router.page("/devices")
async def devices_page() -> None:
    sentinel_server.ui.add_global_style()
    sentinel_server.ui.pages_shared()

    ui.label("Devices")

    table = DevicesTable()

    with ui.row():
        ui.button("Add")

    # Wait for the page to load before refreshing the table.
    await ui.context.client.connected()
    await table.refresh()
