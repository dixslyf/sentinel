import asyncio
import logging
from typing import Optional

import psutil
from aioreactive import AsyncObserver
from nicegui import APIRouter, ui
from nicegui.element import Element
from nicegui.elements.card import Card
from nicegui.elements.markdown import Markdown

import sentinel_server.globals as globals
import sentinel_server.tasks
from sentinel_server.alert import ManagedAlert
from sentinel_server.ui import SharedPageLayout
from sentinel_server.ui.alerts import AlertTable
from sentinel_server.ui.cameras import CameraTable
from sentinel_server.ui.devices import DeviceTable

logger = logging.getLogger(__name__)

router = APIRouter()


class SystemUsageWidget:
    def __init__(self) -> None:
        with ui.element("div").classes("flex gap-2 items-center"):
            self._cpu_usage_markdown: Markdown = ui.markdown("**CPU Usage:**")
            self._cpu_spinner = ui.spinner("dots", color="black")

        with ui.element("div").classes("flex gap-2 items-center"):
            self._memory_usage_markdown: Markdown = ui.markdown("**Memory Usage:**")
            self._memory_spinner = ui.spinner("dots", color="black")

        self._task: Optional[asyncio.Task] = None
        self._run: bool = False

    async def refresh(self) -> None:
        cpu_percent = await sentinel_server.tasks.run_in_thread(
            psutil.cpu_percent, interval=1.0
        )
        self._cpu_spinner.set_visibility(False)
        self._cpu_usage_markdown.set_content(f"**CPU Usage:** {cpu_percent:.1f}%")

        memory_percent = (
            await sentinel_server.tasks.run_in_thread(psutil.virtual_memory)
        ).percent
        self._memory_spinner.set_visibility(False)
        self._memory_usage_markdown.set_content(
            f"**Memory Usage:** {memory_percent:.1f}%"
        )

    def start(self) -> None:
        self._run = True
        self._task = asyncio.create_task(self._update_loop())

        def done_callback(task: asyncio.Task):
            self._task = None

        self._task.add_done_callback(done_callback)

    def stop(self) -> None:
        self._run = False

    async def _update_loop(self) -> None:
        while self._run:
            # Update every second.
            await asyncio.sleep(1)
            await self.refresh()


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
                with ui.element("div").classes("w-full flex flex-col items-center"):
                    with ui.element("div").classes("w-full flex gap-8 justify-center"):
                        system_usage = SystemUsageWidget()
                    
                    with ui.element("div").classes(""):
                        statistic_chart = StatisticsDashboardChart()

    await ui.context.client.connected()

    await camera_table.refresh()
    await device_table.refresh()

    await alert_table.register()
    await alert_table.refresh()

    system_usage.start()

    await statistic_chart.register()
    await statistic_chart.refresh()

    await ui.context.client.disconnected()
    system_usage.stop()
    await alert_table.deregister()
    await statistic_chart.deregister()
