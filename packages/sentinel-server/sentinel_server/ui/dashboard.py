from nicegui import APIRouter, ui

import sentinel_server.ui

router = APIRouter()


@router.page("/dashboard")
def dashboard_page():
    sentinel_server.ui.pages_shared()
    ui.label("dashboard")
