from nicegui import APIRouter, ui

import sentinel_server.ui

router = APIRouter()


@router.page("/settings")
def settings():
    sentinel_server.ui.pages_shared()
    ui.label("settings")
