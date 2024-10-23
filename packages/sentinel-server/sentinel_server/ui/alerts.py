from nicegui import APIRouter, ui

import sentinel_server.ui

router = APIRouter()


@router.page("/alerts")
def alerts_page():
    sentinel_server.ui.pages_shared()
    ui.label("alerts")
