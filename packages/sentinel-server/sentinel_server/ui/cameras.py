import logging

import nicegui
from aioreactive import AsyncObserver
from nicegui import APIRouter, ui
from nicegui.events import GenericEventArguments
from PIL import Image
from sentinel_core.video import Frame

import sentinel_server.globals
import sentinel_server.tasks
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
            "name": "vidstream_plugin_component",
            "label": "Video Stream Plugin / Component",
            "field": "vidstream_plugin_component",
        },
        {
            "name": "detector_plugin_component",
            "label": "Detector Plugin / Component",
            "field": "detector_plugin_component",
        },
        {"name": "status", "label": "Status", "field": "status"},
        {"name": "enabled", "label": "Enabled", "field": "enabled"},
        {"name": "view", "label": "", "field": "view"},
    ]

    def __init__(self) -> None:
        self.table = ui.table(columns=CameraTable.columns, rows=[], row_key="id").props(
            "loading"
        )

        # Enabled checkbox.
        self.table.add_slot(
            "body-cell-enabled",
            '<q-td :props="props">'
            + '<q-checkbox v-model="props.row.enabled" @update:model-value="() => $parent.$emit(\'update_enabled\', props.row)" />\n'
            + "</q-td>",
        )
        self.table.on("update_enabled", self.update_enabled_handler)

        # Link for view.
        self.table.add_slot(
            "body-cell-view",
            '<q-td :props="props">\n'
            + "   <a :href=\"'cameras/' + props.row.id\">View</a>"
            + "</q-td>",
        )

    async def update_enabled_handler(self, msg: GenericEventArguments):
        """
        Handler for when the enabled checkbox for a video source is toggled.
        """
        id = msg.args["id"]
        enabled = msg.args["enabled"]

        vid_src_manager = sentinel_server.globals.video_source_manager
        if enabled:
            await vid_src_manager.enable_video_source(id)
        else:
            await vid_src_manager.disable_video_source(id)

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

        for _, vid_src in vid_src_manager.video_sources.items():
            self.table.add_row(
                {
                    "id": vid_src.id,
                    "name": vid_src.name,
                    "vidstream_plugin_component": f"{vid_src.vidstream_plugin_name} / {vid_src.vidstream_component_name}",
                    "detector_plugin_component": f"{vid_src.detector_plugin_name} / {vid_src.detector_component_name}",
                    "status": "Offline",  # TODO: query global video source manager about status
                    "enabled": vid_src.enabled,
                    "view": vid_src.id,  # TODO: change how this looks
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
        self.vidstream_inputs: dict[str, nicegui.element.Element] = {}

        # Same as the above but for detectors.
        self.detector_inputs: dict[str, nicegui.element.Element] = {}

        with self.dialog, ui.card():
            ui.label("Add Camera")

            # Name of the video source.
            self.name_input = ui.input(label="Name")

            # Selection box for the video stream component.
            self.vidstream_select = ui.select({}, label="Video stream type")

            # Section containing inputs for configuration specific
            # to the video stream component and plugin.
            self.vidstream_section = ui.element("div")

            # Update the form to show configuration inputs for
            # the currently selected video stream component.
            self.vidstream_select.on_value_change(self._update_vidstream_config_inputs)

            # Selection box for the detector component.
            self.detector_select = ui.select({}, label="Detector type")

            # Section containing inputs for configuration specific
            # to the detector component and plugin.
            self.detector_section = ui.element("div")

            # Update the form to show configuration inputs for
            # the currently selected detector component.
            self.detector_select.on_value_change(self._update_detector_config_inputs)

            with ui.grid(columns=2):
                ui.button("Close", on_click=self.close)
                ui.button("Finish", on_click=self._on_finish)

    async def open(self):
        """Opens the dialog."""
        await self._update_vidstream_select_options()
        await self._update_detector_select_options()
        self.dialog.open()

    def close(self):
        """Closes the dialog."""
        self.dialog.close()

    async def _update_vidstream_select_options(self) -> None:
        """Updates the options for the dropdown selection box for the video stream component."""
        await sentinel_server.globals.video_source_manager_loaded.wait()
        vid_src_manager = sentinel_server.globals.video_source_manager
        available_vidstream_comps = vid_src_manager.available_vidstream_components()

        self.vidstream_select.set_options(
            {comp: comp.display_name for comp in available_vidstream_comps}
        )

    async def _update_detector_select_options(self) -> None:
        """Updates the options for the dropdown selection box for the detector component."""
        await sentinel_server.globals.video_source_manager_loaded.wait()
        vid_src_manager = sentinel_server.globals.video_source_manager
        available_detector_comps = vid_src_manager.available_detector_components()

        self.detector_select.set_options(
            {comp: comp.display_name for comp in available_detector_comps}
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
        with self.vidstream_section:
            for arg in comp.args:
                if arg.choices is None:
                    input = ui.input(label=arg.display_name)
                    self.vidstream_inputs[arg.arg_name] = input
                else:
                    select = ui.select(
                        {choice.value: choice.display_name for choice in arg.choices},
                        label=arg.display_name,
                    )
                    self.vidstream_inputs[arg.arg_name] = select

    def _update_detector_config_inputs(
        self, vidstream_select: nicegui.elements.select.Select
    ) -> None:
        """
        Updates the user interface by dynamically adding input fields
        for the currently selected detector component's configuration.

        Args:
            vidstream_select (nicegui.elements.select.Select): The dropdown selection element.
        """
        # TODO: Reduce code duplication with the vidstream counterpart.

        self.detector_inputs = {}
        self.detector_section.clear()

        comp = self.detector_select.value
        with self.detector_section:
            for arg in comp.args:
                if arg.choices is None:
                    input = ui.input(label=arg.display_name)
                    self.detector_inputs[arg.arg_name] = input
                else:
                    select = ui.select(
                        {choice.value: choice.display_name for choice in arg.choices},
                        label=arg.display_name,
                    )
                    self.detector_inputs[arg.arg_name] = select

    async def _on_finish(self) -> None:
        """
        Completes the camera addition process by creating a new video source in the database,
        refreshing the table and closing the dialog.
        """
        # Keyword args for creating the video stream.
        vidstream_kwargs = {
            arg_name: input.value for arg_name, input in self.vidstream_inputs.items()
        }

        # Keyword args for creating the detector.
        detector_kwargs = {
            arg_name: input.value for arg_name, input in self.detector_inputs.items()
        }

        vidstream_comp = self.vidstream_select.value
        detector_comp = self.detector_select.value

        try:
            vid_src_manager = sentinel_server.globals.video_source_manager
            await vid_src_manager.add_video_source(
                self.name_input.value,
                vidstream_comp,
                vidstream_kwargs,
                detector_comp,
                detector_kwargs,
            )
        except Exception as ex:
            ui.notify(f"An error occurred: {ex}", color="negative")

        await self.camera_table.refresh()
        self.close()


@router.page("/cameras")
async def cameras_page() -> None:
    sentinel_server.ui.add_global_style()
    sentinel_server.ui.pages_shared()

    ui.label("Cameras")

    table = CameraTable()

    dialog = AddCameraDialog(table)

    with ui.row():
        ui.button("Add", on_click=dialog.open)

    # Wait for the page to load before refreshing the table.
    await ui.context.client.connected()
    await table.refresh()


class CameraView(AsyncObserver[Frame]):
    def __init__(self, id: int):
        self.id = id
        self.image = ui.interactive_image()

    async def start_capture(self):
        await sentinel_server.globals.video_source_manager_loaded.wait()
        await sentinel_server.globals.video_source_manager_loaded_from_db.wait()

        await sentinel_server.globals.video_source_manager.subscribe_to(self.id, self)

        vid_src = sentinel_server.globals.video_source_manager.video_sources[self.id]
        logger.info(f'Started displaying frames for "{vid_src.name}" (id: {self.id})')

    async def stop_capture(self):
        await sentinel_server.globals.video_source_manager.unsubscribe_from(
            self.id, self
        )

        vid_src = sentinel_server.globals.video_source_manager.video_sources[self.id]
        logger.info(f'Stopped displaying frames for "{vid_src.name}" (id: {self.id})')

    async def asend(self, frame: Frame):
        pil_image = await sentinel_server.tasks.run_in_process(
            Image.fromarray, frame.data
        )
        self.image.set_source(pil_image)

    async def athrow(self, error):
        raise NotImplementedError

    async def aclose(self):
        raise NotImplementedError


@router.page("/cameras/{id}")
async def camera_view_page(id: int) -> None:
    sentinel_server.ui.add_global_style()
    sentinel_server.ui.pages_shared()

    ui.label(f"camera {id}")

    camera_view = CameraView(id)

    await ui.context.client.connected()
    await camera_view.start_capture()

    await ui.context.client.disconnected()
    await camera_view.stop_capture()
