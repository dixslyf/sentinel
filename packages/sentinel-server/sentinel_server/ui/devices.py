from nicegui import APIRouter, ui

import sentinel_server.ui

router = APIRouter()


@router.page("/devices")
def devices_page():
    sentinel_server.ui.pages_shared()
    ui.label("devices")
