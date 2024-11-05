import logging
from typing import Any

from nicegui import APIRouter, ui

import sentinel_server.globals as globals
import sentinel_server.ui
from sentinel_server.alert import ManagedSubscriber
from sentinel_server.ui.alerts import AlertTable
from sentinel_server.ui.cameras import CameraTable
from sentinel_server.ui.devices import DeviceTable

logger = logging.getLogger(__name__)

router = APIRouter()


class StatisticsDashboardChart:
    def __init__(self) -> None:
        self.plot = ui.matplotlib(figsize=(4, 3))

    async def refresh(self) -> None:
        self.plot.clear()

        detection_counts: dict[str, int] = {}
        await globals.alert_manager_loaded.wait()

        async for alert in globals.alert_manager.get_alerts():
            detections = alert.data["detections"]
            for detection in detections:
                detection_counts[detection] = detection_counts.get(detection, 0) + 1

        labels = list(detection_counts.keys())
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


@router.page("/dashboard")
async def dashboard_page() -> None:
    sentinel_server.ui.add_global_style()
    sentinel_server.ui.pages_shared()
    ui.label("Dashboard").classes(
        "px-5 py-2 text-4xl font-bold text-[#4a4e69] border-b-2 border-gray-200 w-full"
    )

    with ui.element("div").classes("w-full flex flex-col items-center"):
        with ui.element("div").classes("flex w-full gap-10 justify-center mt-5"):
            with ui.card().classes(
                "w-2/5 border-2 border-gray-100 rounded-lg shadow-md p-6 hover:shadow-lg hover:scale-105 transform transition dutraion-300"
            ):
                ui.label("Cameras").classes("text-xl font-bold text-[#4a4e69]")
                with ui.element("div").classes("w-full flex justify-center"):
                    camera_table = CameraTable(condensed=True)

            with ui.card().classes(
                "w-2/5 border-2 border-gray-100 rounded-lg shadow-md p-6 hover:shadow-lg hover:scale-105 transform transition dutraion-300"
            ):
                ui.label("Devices").classes("text-xl font-bold text-[#4a4e69]")
                with ui.element("div").classes("w-full flex justify-center"):
                    device_table = DeviceTable(condensed=True)

        with ui.element("div").classes("flex w-full gap-10 justify-center mt-5"):
            with ui.card().classes(
                "w-2/5 border-2 border-gray-100 rounded-lg shadow-md p-6 hover:shadow-lg hover:scale-105 transform transition dutraion-300"
            ):
                ui.label("Alerts").classes("text-xl font-bold text-[#4a4e69]")
                with ui.element("div").classes("w-full flex justify-center"):
                    alert_table = AlertTable(condensed=True)

            with ui.card().classes(
                "w-2/5 border-2 border-gray-100 rounded-lg shadow-md p-6 hover:shadow-lg hover:scale-105 transform transition dutraion-300"
            ):
                ui.label("Statistics").classes("text-xl font-bold text-[#4a4e69]")
                with ui.element("div").classes("w-full flex justify-center"):
                    statistic_chart = StatisticsDashboardChart()

    await ui.context.client.connected()
    await camera_table.refresh()
    await device_table.refresh()
    await alert_table.refresh()
    await statistic_chart.refresh()

    await ui.context.client.disconnected()
