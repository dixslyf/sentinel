import logging

import nicegui
from nicegui import APIRouter, ui
from sentinel_core.plugins import ComponentDescriptor, ComponentKind

import sentinel_server.globals
import sentinel_server.ui
from sentinel_server.models import VideoSource

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
        self.table = ui.table(columns=CameraTable.columns, rows=[], row_key="id")

    async def refresh(self) -> None:
        """
        Refreshes the camera table by clearing existing rows and
        repopulating it with camera source data from the database.
        """
        self.table.rows.clear()
        self.table.update()
        async for vid_src in VideoSource.all():
            self.table.add_row(
                {
                    "id": vid_src.id,
                    "name": vid_src.name,
                    "plugin_component": f"{vid_src.plugin_name} / {vid_src.component_name}",
                    "status": "Offline",  # TODO: query global video source manager about status
                }
            )


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

        # Dictionary that maps a video stream component name to the corresponding
        # component object and plugin name.
        # This is used for two things:
        #   1. Displaying the names of available video stream components for the user to select.
        #   2. Creating the video stream (from the component descriptor) and saving the video source
        #      information to the database when the user completes the input form.
        self.vidstream_comps: dict[str, tuple[ComponentDescriptor, str]] = {}

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
            self.vidstream_select = ui.select([])

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
        self._update_vidstream_comps()
        self.dialog.open()

    def close(self):
        """Closes the dialog."""
        self.dialog.close()

    def _update_vidstream_comps(self):
        """Updates the dictionary of video stream components available."""
        self.vidstream_comps = {
            component.display_name: (component, plugin_desc.name)
            for plugin_desc in sentinel_server.globals.plugin_manager.plugin_descriptors
            for component in plugin_desc.plugin.components
            if component.kind == ComponentKind.VideoStream
        }

        self.vidstream_select.set_options(
            [comp_name for comp_name in self.vidstream_comps.keys()]
        )

    def _update_vidstream_config_inputs(
        self, vidstream_select: nicegui.elements.select.Select
    ):
        """
        Updates the user interface by dynamically adding input fields
        for the currently selected video stream component's configuration.

        Args:
            vidstream_select (nicegui.elements.select.Select): The dropdown selection element.
        """
        self.vidstream_inputs = {}
        self.vidstream_section.clear()
        with self.vidstream_section, ui.grid(columns=2):
            comp, _ = self.vidstream_comps[vidstream_select.value]
            for arg in comp.args:
                ui.label(arg.display_name)
                input = ui.input()
                self.vidstream_inputs[arg.arg_name] = input

    async def _on_finish(self):
        """
        Completes the camera addition process by creating a new video source in the database,
        refreshing the table and closing the dialog.
        """
        # Kwargs for creating the video stream.
        vidstream_kwargs = {
            arg_name: input.value for arg_name, input in self.vidstream_inputs.items()
        }

        comp, plugin_name = self.vidstream_comps[self.vidstream_select.value]

        # Get the video stream class.
        vidstream_cls = comp.cls

        try:
            # Create the video stream.
            # TODO: save the video stream in some global video stream manager
            vidstream = vidstream_cls(**vidstream_kwargs)
            logger.info(vidstream)

            # Create an entry in the database.
            vid_src = VideoSource(
                name=self.name_input.value,
                plugin_name=plugin_name,
                component_name=self.vidstream_select.value,
                config=vidstream_kwargs,
            )
            await vid_src.save()
            logger.info(f'Saved "{vid_src.name}" video source to database')

            await self.camera_table.refresh()
            self.close()
        except Exception as ex:
            ui.notify(f"An error occurred: {ex}", color="negative")


@router.page("/cameras")
async def cameras_page() -> None:
    sentinel_server.ui.pages_shared()

    ui.label("Cameras")

    table = CameraTable()
    await table.refresh()

    dialog = AddCameraDialog(table)

    with ui.row():
        ui.button("Add", on_click=dialog.open)
