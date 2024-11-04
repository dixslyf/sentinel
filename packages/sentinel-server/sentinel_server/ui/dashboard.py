from nicegui import APIRouter, ui

import sentinel_server.ui

router = APIRouter()


@router.page("/dashboard")
def dashboard_page():
    sentinel_server.ui.add_global_style()
    sentinel_server.ui.pages_shared()
    ui.label("Dashboard").classes("px-5 py-2 text-4xl font-bold text-[#4a4e69] border-b-2 border-gray-200 w-full")

