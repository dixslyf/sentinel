import logging

from aioreactive import AsyncObserver
from nicegui import APIRouter, ui
from nicegui.element import Element
from nicegui.elements.card import Card

import sentinel_server.globals as globals
from sentinel_server.alert import ManagedAlert
from sentinel_server.ui import SharedPageLayout
from sentinel_server.ui.alerts import AlertTable
from sentinel_server.ui.cameras import CameraTable
from sentinel_server.ui.devices import DeviceTable

logger = logging.getLogger(__name__)

router = APIRouter()


class StatisticsDashboardChart(AsyncObserver[ManagedAlert]):
    def __init__(self) -> None:
        self.plot = ui.matplotlib(figsize=(4, 3))

    async def register(self) -> None:
        await globals.alert_manager_loaded.wait()
        self._subscription = await globals.alert_manager.subscribe(self)

    async def deregister(self) -> None:
        if self._subscription is not None:
            await self._subscription.dispose_async()

    async def refresh(self) -> None:
        self.plot.clear()

        detection_counts: dict[str, int] = {}
        await globals.alert_manager_loaded.wait()

        async for alert in globals.alert_manager.get_alerts():
            detections = alert.data["detections"]
            for detection in detections:
                detection_counts[detection] = detection_counts.get(detection, 0) + 1

        labels = [label.capitalize() for label in detection_counts.keys()]
        values = list(detection_counts.values())

        ax = self.plot.figure.gca()
        ax.clear()

        if labels and values:
            ax.bar(labels, values, color="#4a4e69")
        else:
            ax.bar([], [])
            ax.text(
                0.5,
                0.5,
                "No detections available",
                ha="center",
                va="center",
                fontsize=12,
                color="grey",
                transform=ax.transAxes,
            )

        ax.set_title("Detected Types in Alerts")

        self.plot.update()

    async def asend(self, alert: ManagedAlert) -> None:
        await self.refresh()

    async def athrow(self, error: Exception) -> None:
        raise NotImplementedError

    async def aclose(self) -> None:
        raise NotImplementedError


def _grid() -> Element:
    return ui.element("div").classes(
        f"grid grid-cols-2 gap-{SharedPageLayout.CONTAINER_PADDING} justify-items-stretch"
    )


def _card_container(title: str) -> Card:
    card = ui.card().classes(
        " ".join(
            (
                "flex",
                "flex-col",
                "border-2",
                "border-gray-100",
                "rounded-lg",
                "shadow-md",
                "p-6",
                "hover:shadow-lg",
                "hover:scale-105",
                "transform",
                "transition",
                "duration-200",
            )
        )
    )

    with card:
        ui.label(title).classes("text-xl font-bold text-[#4a4e69]")

    return card


@router.page("/dashboard")
async def dashboard_page() -> None:
    with SharedPageLayout("Dashboard"):
        with _grid():
            with _card_container("Cameras"):
                camera_table = CameraTable(condensed=True)
            with _card_container("Devices"):
                device_table = DeviceTable(condensed=True)
            with _card_container("Alerts"):
                alert_table = AlertTable(condensed=True)
            with _card_container("Statistics"):
                statistic_chart = StatisticsDashboardChart()

    await ui.context.client.connected()

    await camera_table.refresh()
    await device_table.refresh()

    await alert_table.register()
    await alert_table.refresh()

    await statistic_chart.register()
    await statistic_chart.refresh()

    await ui.context.client.disconnected()
    await alert_table.deregister()
    await statistic_chart.deregister()
