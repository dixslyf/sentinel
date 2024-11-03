import logging
from typing import Any, Optional

from aioreactive import AsyncDisposable, AsyncObserver
from nicegui import APIRouter, ui

import sentinel_server.globals as globals
import sentinel_server.ui
from sentinel_server.alert import ManagedAlert

router = APIRouter()

logger = logging.getLogger(__name__)


class AlertTable(AsyncObserver[ManagedAlert]):
    """
    A table of alerts.

    The table is dynamically populated with alerts retrieved from the database.
    """

    columns: list[dict[str, Any]] = [
        {
            "name": "id",
            "label": "ID",
            "field": "id",
            "required": True,
            "align": "left",
        },
        {
            "name": "header",
            "label": "Header",
            "field": "header",
            "align": "left",
        },
        {
            "name": "description",
            "label": "Description",
            "field": "description",
            "align": "left",
        },
        {
            "name": "source",
            "label": "Source",
            "field": "source",
            "align": "left",
        },
        {
            "name": "timestamp",
            "label": "Timestamp",
            "field": "timestamp",
            "align": "left",
        },
    ]

    def __init__(self) -> None:
        self.table = (
            ui.table(
                columns=AlertTable.columns,
                rows=[],
                row_key="id",
                pagination={"rowsPerPage": 10, "sortBy": "id", "descending": True},
            )
            .props("loading")
            .classes("w-11/12 border-2 border-gray-100")
            .props("table-header-style='background-color: #f0f0f0'")
            .props("flat")
        )

        self._subscription: Optional[AsyncDisposable] = None

    async def register(self) -> None:
        await globals.alert_manager_loaded.wait()
        self._subscription = await globals.alert_manager.subscribe(self)

    async def deregister(self) -> None:
        if self._subscription is not None:
            await self._subscription.dispose_async()

    async def refresh(self) -> None:
        """
        Refreshes the alerts table by clearing existing rows and
        repopulating it with data from the database.
        """
        self.table.rows.clear()
        self.table.update()

        await globals.alert_manager_loaded.wait()

        async for alert in globals.alert_manager.get_alerts():
            self.table.add_row(
                {
                    "id": alert.id,
                    "header": alert.header,
                    "description": alert.description,
                    "source": alert.source,
                    "timestamp": alert.timestamp,
                }
            )

        self.table.props("loading=false")
        self.table.update()

        logger.info("Refreshed alert table")

    async def asend(self, alert: ManagedAlert) -> None:
        self._append_alert(alert)

    async def athrow(self, error: Exception) -> None:
        raise NotImplementedError

    async def aclose(self) -> None:
        raise NotImplementedError

    def _append_alert(self, alert: ManagedAlert) -> None:
        self.table.add_row(
            {
                "id": alert.id,
                "header": alert.header,
                "description": alert.description,
                "source": alert.source,
                "timestamp": alert.timestamp,
            }
        )


@router.page("/alerts")
async def alerts_page():
    sentinel_server.ui.add_global_style()
    sentinel_server.ui.pages_shared()
    ui.label("alerts")

    alert_table = AlertTable()
    await alert_table.refresh()
    await alert_table.register()

    await ui.context.client.disconnected()
    alert_table.deregister()
