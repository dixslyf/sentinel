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

    def __init__(
        self, source_id: Optional[int] = None, condensed: bool = False
    ) -> None:
        columns: list[dict[str, Any]] = (
            AlertTable.columns
            if not condensed
            else [
                column
                for column in AlertTable.columns
                if column["name"] in {"description", "source", "timestamp"}
            ]
        )

        self.table = (
            ui.table(
                columns=columns,
                rows=[],
                row_key="id",
                pagination={
                    "rowsPerPage": 5 if condensed else 10,
                    "sortBy": "id",
                    "descending": True,
                },
            )
            .props("loading")
            .classes("w-11/12 border-2 border-gray-100")
            .props("table-header-style='background-color: #f0f0f0'")
            .props("flat")
        )

        self.source_id = source_id

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

        source_name: Optional[str]
        if self.source_id:
            await globals.video_source_manager_loaded.wait()
            await globals.video_source_manager_loaded_from_db.wait()
            vid_src = globals.video_source_manager.video_sources[self.source_id]
            source_name = vid_src.name
        else:
            source_name = None

        await globals.alert_manager_loaded.wait()

        async for alert in globals.alert_manager.get_alerts(source_name):
            self.table.add_row(
                {
                    "id": alert.id,
                    "header": alert.header,
                    "description": alert.description,
                    "source": (
                        alert.source
                        if not alert.source_deleted
                        else f"{alert.source} (deleted)"
                    ),
                    # .astimezone() converts from UTC to the local time zone.
                    # .strftime() for formatting.
                    "timestamp": alert.timestamp.astimezone().strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
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

    ui.label("Alerts").classes(
        "px-5 py-2 text-4xl font-bold text-[#4a4e69] border-b-2 border-gray-200 w-full"
    )
    with ui.element("div").classes("flex justify-center text-center w-full mt-5"):
        alert_table = AlertTable()

    await alert_table.refresh()
    await alert_table.register()

    await ui.context.client.disconnected()
    await alert_table.deregister()
