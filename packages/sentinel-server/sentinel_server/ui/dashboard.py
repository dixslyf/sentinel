import logging
from typing import Any

from nicegui import APIRouter, ui
from nicegui.events import GenericEventArguments

import sentinel_server.ui
import sentinel_server.globals as globals
from sentinel_server.video import VideoSourceStatus
from sentinel_server.alert import ManagedSubscriber, SubscriberStatus

logger = logging.getLogger(__name__)

router = APIRouter()

class CameraDashboardTable: 
    columns: list[dict[str, Any]] = [
        {
            "name": "name",
            "label": "Name",
            "field": "name",
            "align": "left", 
            "required": True,
        },
        {
            "name": "status",
            "label": "Status",
            "field": "status",
            "align": "center",
        },
        {
            "name": "quick_access",
            "label": "",
            "field": "quick_access",
        }
    ]

    def __init__(self) -> None: 
        self.table = (
            ui.table(columns=CameraDashboardTable.columns, rows=[], row_key="name")
            .props("loading")
            .classes("w-10/12 border-2 border-gray-100")
            .props("table-header-style='background-color: #f0f0f0'")
            .props("flat")
        )

        # status indicator slot
        self.table.add_slot(
            "body-cell-status",
            '<q-td :props="props">'
            + "<q-icon :name='props.row.status === \"OK\" ? \"check_circle\" : \"error\"' "
            + ":color='props.row.status === \"OK\" ? \"green\" : \"red\"' />"
            + '</q-td>'
        )

        # quick access button slot
        self.table.add_slot(
            "body-cell-quick_access",
            '<q-td :props="props">'
            + "   <a :href=\"'cameras/' + props.row.id\" :class=\"'hover:bg-gray-100'\">{{props.row.quick_access}}</a>"
            + "</q-td>"
        )

    async def refresh(self) -> None: 
        self.table.rows.clear()
        self.table.update()

        await globals.video_source_manager_loaded.wait()
        await globals.video_source_manager_loaded_from_db.wait()

        vid_src_manager = globals.video_source_manager

        for _, vid_src in vid_src_manager.video_sources.items():
            self.table.add_row(
                {
                    "id": vid_src.id,
                    "name": vid_src.name,
                    "status": "OK" if vid_src.status == VideoSourceStatus.Ok else "Error",
                    "quick_access": "View",
                }
            )
        
        self.table.props("loading=false")
        logger.debug("Refreshed camera dashboard table")

class DeviceDashboardTable:
    columns: list[dict[str, Any]] = [
        {
            "name": "id",
            "label": "ID",
            "field": "id",
            "required": "True",
            "align": "left",
        },
        {
            "name": "name",
            "label": "Name",
            "field": "name",
            "required": "True",
            "align": "left",
        },
        {
            "name": "type",
            "label": "Type",
            "field": "type",
            "align": "left",
        },
        {
            "name": "status",
            "label": "Status",
            "field": "status",
            "align": "center",
        },
        {
            "name": "quick_access",
            "label": "",
            "field": "quick_access",
        }
    ]

    def __init__(self) -> None:
        self.table = (
            ui.table(columns=DeviceDashboardTable.columns, rows=[], row_key="name")
            .props("loading")
            .classes("w-10/12 border-2 border-gray-100")
            .props("table-header-style='background-color: #f0f0f0'")
            .props("flat")
        )

        # status indicator slot 
        self.table.add_slot(
            "body-cell-status",
            '<q-td :props="props">'
            + "<q-icon :name='props.row.status === \"OK\" ? \"check_circle\" : \"error\"' "
            + ":color='props.row.status === \"OK\" ? \"green\" : \"red\"' />"
            + '</q-td>'
        )

        # link for view
        self.table.add_slot(
            "body-cell-quick_access",
            '<q-td :props="props">\n'
            + "   <a :href=\"'devices/' + props.row.id\">{{props.row.quick_access}}</a>"
            + "</q-td>",
        )
    
    async def refresh(self) -> None: 
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
                    "type": sub.component_name,
                    "status": "OK" if sub.status == SubscriberStatus.Ok else "Error",
                    "quick_access": "View",
                }
            )
        
        self.table.props("loading=false")
        self.table.update()
        logger.debug("Refreshed devices table")

class AlertDashboardTable: 
    columns: list[dict[str, Any]] = [
        {
            "name": "id",
            "label": "ID",
            "field": "id",
            "align": "left",
            "required": True,
        },
        {
            "name": "description",
            "label": "Detected", 
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
                    columns=AlertDashboardTable.columns, 
                    rows=[], 
                    row_key="id",
                    pagination={"rowsPerPage": 3, "sortBy": "id", "descending": True},
                )
                .props("loading")
                .classes("w-11/12 border-2 border-gray-100")
                .props("table-header-style='background-color: #f0f0f0'")
                .props("flat")
        )
    
    async def refresh(self) -> None:
        self.table.rows.clear()
        self.table.update()

        await globals.alert_manager_loaded.wait()

        async for alert in globals.alert_manager.get_alerts():
            self.table.add_row(
                {
                    "id": alert.id,
                    "description": alert.description,
                    "source": alert.source,
                    "timestamp": alert.timestamp,
                }
            )
        
        self.table.props("loading=false")
        self.table.update()

        logger.debug("Refreshed alert dashboard table")

    
class StatisticsDashboardChart:
    def __init__(self) -> None: 
        self.plot = ui.matplotlib(figsize=(4, 3))
    
    async def refresh(self) -> None: 
        self.plot.clear()

        detection_counts = {}
        await globals.alert_manager_loaded.wait()

        async for alert in globals.alert_manager.get_alerts():
            # logger.info(f"Detections: {alert.data["detections"]}")
            # print(f"detection: {alert.data["detections"]}")
            detections = alert.data["detections"]
            for detection in detections: 
                detection_counts[detection] = detection_counts.get(detection, 0) + 1
        
        # logger.info(f"Detection Counts: {detection_counts}")
        labels = list(detection_counts.keys())
        values = list(detection_counts.values())

        ax = self.plot.figure.gca()
        ax.clear()

        if labels and values: 
            ax.bar(labels, values, color="#4a4e69")
        else: 
            ax.bar([], [])
            ax.text(0.5, 0.5, "No detections available", ha='center', va='center', fontsize=12, color='grey', transform=ax.transAxes)

        ax.set_title("Detected Types in Alerts")

        self.plot.update()

@router.page("/dashboard")  
async def dashboard_page() -> None:
    sentinel_server.ui.add_global_style()
    sentinel_server.ui.pages_shared()
    ui.label("Dashboard").classes("px-5 py-2 text-4xl font-bold text-[#4a4e69] border-b-2 border-gray-200 w-full")

    with ui.element("div").classes("w-full flex flex-col items-center"):
        with ui.element("div").classes("flex w-full gap-10 justify-center mt-5"):
            with ui.card().classes("w-2/5 border-2 border-gray-100 rounded-lg shadow-md p-6 hover:shadow-lg hover:scale-105 transform transition dutraion-300"):
                ui.label("Cameras").classes("text-xl font-bold text-[#4a4e69]")
                with ui.element("div").classes("w-full flex justify-center"):
                    camera_table = CameraDashboardTable() 
            
            with ui.card().classes("w-2/5 border-2 border-gray-100 rounded-lg shadow-md p-6 hover:shadow-lg hover:scale-105 transform transition dutraion-300"):
                ui.label("Devices").classes("text-xl font-bold text-[#4a4e69]")
                with ui.element("div").classes("w-full flex justify-center"):
                    device_table = DeviceDashboardTable()

        with ui.element("div").classes("flex w-full gap-10 justify-center mt-5"):
            with ui.card().classes("w-2/5 border-2 border-gray-100 rounded-lg shadow-md p-6 hover:shadow-lg hover:scale-105 transform transition dutraion-300"):
                ui.label("Alerts").classes("text-xl font-bold text-[#4a4e69]")
                with ui.element("div").classes("w-full flex justify-center"):
                    alert_table = AlertDashboardTable()

            with ui.card().classes("w-2/5 border-2 border-gray-100 rounded-lg shadow-md p-6 hover:shadow-lg hover:scale-105 transform transition dutraion-300"):
                ui.label("Statistics").classes("text-xl font-bold text-[#4a4e69]")
                with ui.element("div").classes("w-full flex justify-center"):
                    statistic_chart = StatisticsDashboardChart()
    

    await ui.context.client.connected()
    await camera_table.refresh()
    await device_table.refresh()
    await alert_table.refresh()
    await statistic_chart.refresh()

    await ui.context.client.disconnected()