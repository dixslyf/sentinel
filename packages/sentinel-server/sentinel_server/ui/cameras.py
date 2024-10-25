import logging

import nicegui
from nicegui import APIRouter, ui

import sentinel_server.globals
import sentinel_server.ui

logger = logging.getLogger(__name__)

router = APIRouter()


class CameraTable:
    """
    Represents a table of camera sources in the UI.

    The table is dynamically populated with video sources retrieved from the database.
    """

    columns = [
        {
            "name": "id",
            "label": "ID",
            "field": "id",
            "required": True,
            "align": "middle",
        },
        {"name": "name", "label": "Name", "field": "name"},
        {
            "name": "plugin_component",
            "label": "Plugin / Component",
            "field": "plugin_component",
        },
        {"name": "status", "label": "Status", "field": "status"},
    ]

    def __init__(self) -> None:
        self.table = ui.table(columns=CameraTable.columns, rows=[], row_key="id").props(
            "loading"
        )

    async def refresh(self) -> None:
        """
        Refreshes the camera table by clearing existing rows and
        repopulating it with camera source data from the database.
        """
        self.table.rows.clear()
        self.table.update()

        # Wait for:
        # - The video source manager to be initialised
        # - The video source manager to load video sources from the database
        #
        # In most user scenarios, we don't have to wait for the video source manager,
        # but, during development, hot-reloading can cause the table to try to refresh
        # before the video source manager has been initialised or before it has loaded
        # the video sources.
        await sentinel_server.globals.video_source_manager_loaded.wait()
        await sentinel_server.globals.video_source_manager_loaded_from_db.wait()

        vid_src_manager = sentinel_server.globals.video_source_manager

        for _, vid_src in vid_src_manager.video_sources().items():
            self.table.add_row(
                {
                    "id": vid_src.id,
                    "name": vid_src.name,
                    "plugin_component": f"{vid_src.plugin_name} / {vid_src.component_name}",
                    "status": "Offline",  # TODO: query global video source manager about status
                }
            )

        self.table.props("loading=false")
        logger.debug("Refreshed camera table")


class AddCameraDialog:
    """
    Represents a dialog for adding new camera sources.

    Input fields are dynamically created and rendered based on the selected video stream component,
    allowing the user to enter custom configuration for the camera source.
    """

    def __init__(self, camera_table: CameraTable) -> None:
        """
        Initialises the dialog with the given camera table reference.

        The camera table reference is needed to refresh the table when the user has finished
        entering data for a camera source.

        Args:
            camera_table (CameraTable): The camera table instance to refresh after adding a new camera.
        """
        self.camera_table = camera_table

        self.dialog = ui.dialog()

        # Dictionary that maps each argument display name of the currently selected
        # video stream component to a NiceGUI input box. Used for retrieving the user's
        # inputs when they complete the form.
        self.vidstream_inputs: dict[str, nicegui.elements.input.Input] = {}

        with self.dialog, ui.card(), ui.grid(columns=2):
            # Name of the video source.
            self.name_label = ui.label("Name")
            self.name_input = ui.input()

            # Selection box for the video stream component.
            self.plugin_label = ui.label("Video stream type:")
            self.vidstream_select = ui.select({})

            # Card section containing inputs for configuration specific
            # to the video stream component and plugin.
            self.vidstream_section = ui.card_section().classes("col-span-2")

            # Update the form to show configuration inputs for
            # the currently selected video stream component.
            self.vidstream_select.on_value_change(self._update_vidstream_config_inputs)

            ui.button("Close", on_click=self.close)
            ui.button("Finish", on_click=self._on_finish)

    def open(self):
        """Opens the dialog."""
        self._update_vidstream_select_options()
        self.dialog.open()

    def close(self):
        """Closes the dialog."""
        self.dialog.close()

    def _update_vidstream_select_options(self) -> None:
        """Updates the options for the dropdown selection box for the video stream component."""
        vid_src_manager = sentinel_server.globals.video_source_manager
        available_vidstream_comps = vid_src_manager.available_vidstream_components()

        self.vidstream_select.set_options(
            {comp: comp.display_name for comp in available_vidstream_comps}
        )

    def _update_vidstream_config_inputs(
        self, vidstream_select: nicegui.elements.select.Select
    ) -> None:
        """
        Updates the user interface by dynamically adding input fields
        for the currently selected video stream component's configuration.

        Args:
            vidstream_select (nicegui.elements.select.Select): The dropdown selection element.
        """
        self.vidstream_inputs = {}
        self.vidstream_section.clear()

        comp = self.vidstream_select.value
        with self.vidstream_section, ui.grid(columns=2):
            for arg in comp.args:
                ui.label(arg.display_name)
                input = ui.input()
                self.vidstream_inputs[arg.arg_name] = input

    async def _on_finish(self) -> None:
        """
        Completes the camera addition process by creating a new video source in the database,
        refreshing the table and closing the dialog.
        """
        # Keyword args for creating the video stream.
        vidstream_kwargs = {
            arg_name: input.value for arg_name, input in self.vidstream_inputs.items()
        }

        comp = self.vidstream_select.value

        try:
            vid_src_manager = sentinel_server.globals.video_source_manager
            await vid_src_manager.add_video_source(
                self.name_input.value, comp, vidstream_kwargs
            )
        except Exception as ex:
            ui.notify(f"An error occurred: {ex}", color="negative")

        await self.camera_table.refresh()
        self.close()


@router.page("/cameras")
async def cameras_page() -> None:
    sentinel_server.ui.pages_shared()

    ui.label("Cameras")

    table = CameraTable()

    dialog = AddCameraDialog(table)

    with ui.row():
        ui.button("Add", on_click=dialog.open)

    # Wait for the page to load before refreshing the table.
    await ui.context.client.connected()
    await table.refresh()
