import logging

from nicegui import APIRouter, ui
from sentinel_core.plugins import ComponentKind

import sentinel_server.globals
import sentinel_server.ui

logger = logging.getLogger(__name__)

router = APIRouter()


@router.page("/cameras")
def cameras_page() -> None:
    sentinel_server.ui.pages_shared()

    ui.label("Cameras")
    columns = [
        {
            "name": "id",
            "label": "ID",
            "field": "id",
            "required": True,
            "align": "middle",
        },
        {"name": "name", "label": "Name", "field": "name"},
        {"name": "status", "label": "Status", "field": "status"},
    ]

    rows = [
        {"id": "1", "name": "Example camera", "status": "online"},
    ]

    ui.table(columns=columns, rows=rows, row_key="id")

    vidstream_comps = {
        component.display_name: component
        for component in sentinel_server.globals.plugin_manager.components(
            ComponentKind.VideoStream
        )
    }
    detector_comps = {
        component.display_name: component
        for component in sentinel_server.globals.plugin_manager.components(
            ComponentKind.Detector
        )
    }

    # Dialog for adding a new video stream.
    # TODO: WIP
    with ui.dialog() as dialog, ui.card():
        with ui.grid(columns=2):
            ui.label("Name")
            name_input = ui.input()

            # Video stream options.
            ui.label("Video Stream Plugin:")
            vidstream_select = ui.select([comp_name for comp_name in vidstream_comps])
            vidstream_section = ui.card_section().classes("col-span-2")
            vidstream_inputs: dict = {}

            def show_vidstream_options(el):
                nonlocal vidstream_inputs
                vidstream_inputs = {}
                vidstream_section.clear()
                with vidstream_section, ui.grid(columns=2):
                    for arg in vidstream_comps[el.value].args:
                        ui.label(arg.display_name)
                        input = ui.input()
                        vidstream_inputs[arg.arg_name] = input

            vidstream_select.on_value_change(show_vidstream_options)

            # Detector options.
            ui.label("Detector Plugin:")
            detector_select = ui.select([comp_name for comp_name in detector_comps])
            detector_section = ui.card_section().classes("col-span-2")

            def show_detector_options(el):
                detector_section.clear()
                with detector_section:
                    ui.label(el.value)

            detector_select.on_value_change(show_detector_options)

            ui.button("Close", on_click=dialog.close)

            def on_finish():
                vidstream_kwargs = {
                    arg_name: input.value
                    for arg_name, input in vidstream_inputs.items()
                }

                vidstream_cls = vidstream_comps[vidstream_select.value].cls
                try:
                    vidstream = vidstream_cls(**vidstream_kwargs)
                    logger.info(vidstream)
                    dialog.close()
                except Exception as ex:
                    ui.notify(f"An error occurred: {ex.message()}", color="negative")

            ui.button("Finish", on_click=on_finish)

    with ui.row():
        ui.button("Add", on_click=lambda: dialog.open())
