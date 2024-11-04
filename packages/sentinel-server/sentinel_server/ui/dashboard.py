from nicegui import APIRouter, ui

import sentinel_server.ui

router = APIRouter()


@router.page("/dashboard")
def dashboard_page():
    sentinel_server.ui.add_global_style()
    sentinel_server.ui.pages_shared()
    ui.label("Dashboard").classes("px-5 py-2 text-4xl font-bold text-[#4a4e69] border-b-2 border-gray-200 w-full")

    with ui.element("div").classes("w-full flex justify-center"):
        with ui.grid(columns=2):
            with ui.card():
                ui.label("Cameras")
                # TODO 
                # for this card should include cam name, cam status(green or red icon), and quick access btn
            
            with ui.card():
                ui.label("Devices")
                # TODO
                # for this card should include device name, device status(green or red icon), device type, and quick access btn

            with ui.card():
                ui.label("Alerts")
                # TODO
                # for this card should include timestamp, source, quick access

            with ui.card():
                ui.label("Statistics")
                # TODO 
                # This card is optional but if possible to get detected types 
                # then will be able to do simple bar chart on detected types