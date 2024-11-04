import logging
from typing import Any, Optional

from aioreactive import AsyncDisposable, AsyncObserver
from nicegui import APIRouter, ui
from nicegui.element import Element
from nicegui.elements.input import Input
from nicegui.elements.select import Select
from nicegui.events import (
    ClickEventArguments,
    GenericEventArguments,
    ValueChangeEventArguments,
)
from PIL import Image
from sentinel_core.plugins import ComponentArgDescriptor, ComponentDescriptor
from sentinel_core.video import Frame

import sentinel_server.globals as globals
import sentinel_server.tasks
import sentinel_server.ui
from sentinel_server.ui.alerts import AlertTable
from sentinel_server.ui.utils import ConfirmationDialog
from sentinel_server.video import VideoSource, VideoSourceStatus
from sentinel_server.video.detect import ReactiveDetectionVisualiser

logger = logging.getLogger(__name__)

router = APIRouter()


class CameraTable:
    """
    Represents a table of camera sources in the UI.

    The table is dynamically populated with video sources retrieved from the database.
    """

    columns: list[dict[str, Any]] = [
        {
            "name": "id",
            "label": "ID",
            "field": "id",
            "required": True,
            "align": "left",
        },
        {
            "name": "name",
            "label": "Name",
            "field": "name",
            "align": "left",
            # "headerClasses": "border-l-2 "
        },
        {
            "name": "vidstream_plugin_component",
            "label": "Video Stream Plugin / Component",
            "field": "vidstream_plugin_component",
            "align": "left",
        },
        {
            "name": "detector_plugin_component",
            "label": "Detector Plugin / Component",
            "field": "detector_plugin_component",
            "align": "left",
        },
        {
            "name": "status",
            "label": "Status",
            "field": "status",
            "align": "left",
        },
        {
            "name": "enabled",
            "label": "Enabled",
            "field": "enabled",
            "align": "middle",
        },
        {"name": "view", "label": "", "field": "view"},
    ]

    def __init__(self) -> None:
        self.table = (
            ui.table(columns=CameraTable.columns, rows=[], row_key="id")
            .props("loading")
            .classes("camera_table w-11/12 border-2 border-gray-100")
            .props("table-header-style='background-color: #f0f0f0'")
            .props("flat")
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
            + "   <a :href=\"'cameras/' + props.row.id\">{{props.row.view}}</a>"
            + "</q-td>",
        )

    async def update_enabled_handler(self, msg: GenericEventArguments):
        """
        Handler for when the enabled checkbox for a video source is toggled.
        """
        id = msg.args["id"]
        enabled = msg.args["enabled"]

        row = next((r for r in self.table.rows if r["id"] == id), None)
        assert row is not None

        vid_src_manager = globals.video_source_manager
        if enabled:
            await vid_src_manager.enable_video_source(id)
            row["enabled"] = True
        else:
            await vid_src_manager.disable_video_source(id)
            row["enabled"] = False
        self.table.update()

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
        await globals.video_source_manager_loaded.wait()
        await globals.video_source_manager_loaded_from_db.wait()

        vid_src_manager = globals.video_source_manager

        for _, vid_src in vid_src_manager.video_sources.items():
            self.table.add_row(
                {
                    "id": vid_src.id,
                    "name": vid_src.name,
                    "vidstream_plugin_component": f"{vid_src.vidstream_plugin_name} / {vid_src.vidstream_component_name}",
                    "detector_plugin_component": f"{vid_src.detector_plugin_name} / {vid_src.detector_component_name}",
                    "status": (
                        "OK" if vid_src.status == VideoSourceStatus.Ok else "Error"
                    ),
                    "enabled": vid_src.enabled,
                    "view": "View",
                }
            )

        self.table.props("loading=false")
        logger.debug("Refreshed camera table")

    def on_status_change(self, vid_src: VideoSource) -> None:
        id = vid_src.id

        logger.info(
            f'Updating status for video source "{vid_src.name}" (id: {vid_src.id}): {vid_src.status}'
        )

        # Find the corresponding row.
        for row in self.table.rows:
            if row["id"] == id:
                row["status"] = (
                    "OK" if vid_src.status == VideoSourceStatus.Ok else "Error"
                )
                row["enabled"] = vid_src.enabled
                break

        self.table.update()

    async def register_status_changes(self) -> None:
        await globals.video_source_manager_loaded.wait()
        globals.video_source_manager.add_status_change_callback(self.on_status_change)
        logger.info("Registered status change callback for cameras table")

    async def deregister_status_changes(self) -> None:
        await globals.video_source_manager_loaded.wait()
        globals.video_source_manager.remove_status_change_callback(
            self.on_status_change
        )
        logger.info("Deregistered status change callback for cameras table")


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
        self.vidstream_inputs: dict[str, Input | Select] = {}

        # Same as the above but for detectors.
        self.detector_inputs: dict[str, Input | Select] = {}

        with self.dialog, ui.card().classes("dialog-popup w-1/5"):
            with ui.element("div").classes("w-full flex justify-between"):
                ui.label("Add Camera").classes("flex items-center text-xl bold")
                # close button
                with ui.button(on_click=self.close).props("flat").classes("w-10"):
                    ui.icon("close").classes("text-gray-400")

            # Name of the video source.
            self.name_input = ui.input(label="Name").classes("w-full")

            # Selection box for the video stream component.
            self.vidstream_select = ui.select({}, label="Video stream type").classes(
                "w-full"
            )

            # Section containing inputs for configuration specific
            # to the video stream component and plugin.
            self.vidstream_section = ui.element("div").classes("w-full")

            # Update the form to show configuration inputs for
            # the currently selected video stream component.
            self.vidstream_select.on_value_change(self._update_vidstream_config_inputs)

            # Selection box for the detector component.
            self.detector_select = ui.select({}, label="Detector type").classes(
                "w-full"
            )

            # Section containing inputs for configuration specific
            # to the detector component and plugin.
            self.detector_section = ui.element("div").classes("w-full")

            # Update the form to show configuration inputs for
            # the currently selected detector component.
            self.detector_select.on_value_change(self._update_detector_config_inputs)

            self.interval_input = ui.number(
                label="Detection Interval (seconds)", value=1.0, min=0.0
            ).classes("w-full")

            with ui.element("div").classes("w-full flex justify-end"):
                ui.button("Finish", on_click=self._on_finish).classes(
                    "text-white bg-black"
                )

    async def open(self):
        """
        Opens the dialog, or if no video stream or detector components are available,
        shows a notification to the user to prompt them to install and enable plugins.
        """
        if not (
            await self._check_vidstream_select_options()
            and await self._check_detector_select_options()
        ):
            ui.notify(
                "No video stream or detector plugins enabled. "
                "Plugins can be managed from the Settings page."
            )
            return

        await self._update_vidstream_select_options()
        await self._update_detector_select_options()
        self.dialog.open()

    def close(self):
        """Closes the dialog."""
        self.dialog.close()

    async def _check_vidstream_select_options(self) -> bool:
        await globals.video_source_manager_loaded.wait()
        vid_src_manager = globals.video_source_manager
        available_vidstream_comps = vid_src_manager.available_vidstream_components()
        return len(available_vidstream_comps) > 0

    async def _check_detector_select_options(self) -> bool:
        await globals.video_source_manager_loaded.wait()
        vid_src_manager = globals.video_source_manager
        available_detector_comps = vid_src_manager.available_detector_components()
        return len(available_detector_comps) > 0

    async def _update_vidstream_select_options(self) -> None:
        """Updates the options for the dropdown selection box for the video stream component."""
        await globals.video_source_manager_loaded.wait()
        vid_src_manager = globals.video_source_manager
        available_vidstream_comps = vid_src_manager.available_vidstream_components()

        self.vidstream_select.set_options(
            {comp: comp.display_name for comp in available_vidstream_comps}
        )

    async def _update_detector_select_options(self) -> None:
        """Updates the options for the dropdown selection box for the detector component."""
        await globals.video_source_manager_loaded.wait()
        vid_src_manager = globals.video_source_manager
        available_detector_comps = vid_src_manager.available_detector_components()

        self.detector_select.set_options(
            {comp: comp.display_name for comp in available_detector_comps}
        )

    @staticmethod
    def _update_config_inputs(
        select: Select, section: Element, inputs: dict[str, Input | Select]
    ) -> None:
        inputs.clear()
        section.clear()

        comp: ComponentDescriptor = select.value
        with section:
            arg: ComponentArgDescriptor
            for arg in comp.args:
                if arg.choices is None:
                    input = ui.input(label=arg.display_name)
                    inputs[arg.arg_name] = input
                else:
                    select = ui.select(
                        {choice.value: choice.display_name for choice in arg.choices},
                        label=arg.display_name,
                    )
                    inputs[arg.arg_name] = select

    def _update_vidstream_config_inputs(self, args: ValueChangeEventArguments) -> None:
        """
        Updates the user interface by dynamically adding input fields
        for the currently selected video stream component's configuration.
        """
        self._update_config_inputs(
            self.vidstream_select, self.vidstream_section, self.vidstream_inputs
        )

    def _update_detector_config_inputs(self, args: ValueChangeEventArguments) -> None:
        """
        Updates the user interface by dynamically adding input fields
        for the currently selected detector component's configuration.
        """
        self._update_config_inputs(
            self.detector_select, self.detector_section, self.detector_inputs
        )

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
            vid_src_manager = globals.video_source_manager
            await vid_src_manager.add_video_source(
                self.name_input.value,
                self.interval_input.value,
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

    # ui design for cameras page
    with ui.element("div").classes(
        "camera_wrapper w-full flex flex-col gap-5 justify-center text-center mt-10"
    ):

        with ui.element("div").classes("flex justify-center text-center"):
            table = CameraTable()
            dialog = AddCameraDialog(table)

        with ui.element("div").classes("w-full flex justify-center"):
            with ui.element("div").classes("w-11/12 flex justify-end"):
                ui.button("Add", on_click=dialog.open).classes(
                    "bg-black rounded-xl py-1 px-3 text-[#cad3f5]"
                ).props("no-caps")

    # Wait for the page to load before refreshing the table.
    await ui.context.client.connected()
    await table.refresh()
    await table.register_status_changes()

    await ui.context.client.disconnected()
    await table.deregister_status_changes()


class CameraView(AsyncObserver[Frame]):
    def __init__(self, id: int):
        self.id = id
        self.image = ui.interactive_image().classes("px-5")

        self.visualiser = ReactiveDetectionVisualiser()
        self.sub: Optional[AsyncDisposable] = None

    async def start_capture(self):
        await globals.video_source_manager_loaded.wait()
        await globals.video_source_manager_loaded_from_db.wait()

        await globals.video_source_manager.subscribe_to(self.id, self.visualiser)

        self.sub = await self.visualiser.subscribe_async(self)

        vid_src = globals.video_source_manager.video_sources[self.id]
        logger.info(f'Started displaying frames for "{vid_src.name}" (id: {self.id})')

    async def stop_capture(self):
        await globals.video_source_manager.unsubscribe_from(self.id, self.visualiser)

        await self.sub.dispose_async()

        vid_src = globals.video_source_manager.video_sources[self.id]
        logger.info(f'Stopped displaying frames for "{vid_src.name}" (id: {self.id})')

    async def asend(self, frame: Frame):
        pil_image = Image.fromarray(frame.data)
        self.image.set_source(pil_image)

    async def athrow(self, error):
        raise NotImplementedError

    async def aclose(self):
        raise NotImplementedError


class CameraDetails:
    def __init__(self, vidsrc_id: int):
        self.vidsrc_id: int = vidsrc_id

        # UI elements
        # TODO: make this skeleton element larger
        self.skeleton = ui.skeleton()

        self.id_markdown = ui.markdown()
        self.name_markdown = ui.markdown()
        self.enabled_markdown = ui.markdown()
        self.status_markdown = ui.markdown()
        self.detect_interval_markdown = ui.markdown()

        self.vidstream_plugin_comp_markdown = ui.markdown()
        # TODO: use separate markdowns for individual configuration parameters
        self.vidstream_config_markdown = ui.markdown()

        self.detector_plugin_comp_markdown = ui.markdown()
        # TODO: use separate markdowns for individual configuration parameters
        self.detector_config_markdown = ui.markdown()

        # List of all the markdown elements above so that we can iterate over them easily.
        self._markdown_elements = [
            self.id_markdown,
            self.name_markdown,
            self.enabled_markdown,
            self.status_markdown,
            self.detect_interval_markdown,
            self.vidstream_plugin_comp_markdown,
            self.vidstream_config_markdown,
            self.detector_plugin_comp_markdown,
            self.detector_config_markdown,
        ]

        # Make all markdown elements invisible first so that we only
        # show the skeleton element.
        # They will be made visible once the data has been loaded.
        for markdown_el in self._markdown_elements:
            markdown_el.set_visibility(False)

    async def fill_info(self) -> None:
        await globals.video_source_manager_loaded.wait()
        await globals.video_source_manager_loaded_from_db.wait()

        vidsrc = globals.video_source_manager.video_sources[self.vidsrc_id]

        # Binding means that the UI element will automatically be updated
        # when the corresponding video source attribute gets updated.
        # `backward` is a function applied to the attribute before displaying it
        # (in this case, `backward` should return markdown).
        self.id_markdown.bind_content_from(
            vidsrc, "id", backward=lambda id: f"**ID:** {id}"
        )

        self.name_markdown.bind_content_from(
            vidsrc, "name", backward=lambda name: f"**Name:** {name}"
        )

        self.enabled_markdown.bind_content_from(
            vidsrc,
            "Enabled",
            backward=lambda enabled: f"**Enabled:** {"Yes" if enabled else "No"}",
        )

        self.status_markdown.bind_content_from(
            vidsrc,
            "status",
            backward=lambda status: f"**Status:** {"OK" if status == VideoSourceStatus.Ok else "Error"}",
        )

        self.detect_interval_markdown.bind_content_from(
            vidsrc,
            "detect_interval",
            backward=lambda detect_interval: f"**Detect Interval:** {detect_interval} {"second" if detect_interval == 1 else "seconds"}",
        )

        self.vidstream_plugin_comp_markdown.bind_content_from(
            vidsrc,
            "vidstream_plugin_name",
            backward=lambda vidstream_plugin_name: f"**Video stream type:** {vidstream_plugin_name} / {vidsrc.vidstream_component_name}",
        )

        self.vidstream_config_markdown.bind_content_from(
            vidsrc,
            "vidstream_config",
            backward=lambda vidstream_config: f"**Video stream configuration:** {vidstream_config}",
        )

        self.detector_plugin_comp_markdown.bind_content_from(
            vidsrc,
            "detector_plugin_name",
            backward=lambda detector_plugin_name: f"**Detector type:** {detector_plugin_name} / {vidsrc.detector_component_name}",
        )

        self.detector_config_markdown.bind_content_from(
            vidsrc,
            "detector_config",
            backward=lambda detector_config: f"**Detector configuration:** {detector_config}",
        )

        # Once ready, hide the skeleton and show all markdown elements.
        self.skeleton.set_visibility(False)
        for markdown_el in self._markdown_elements:
            markdown_el.set_visibility(True)


class CameraDeleteButton:
    def __init__(self, vidsrc_id: int) -> None:
        self.vidsrc_id = vidsrc_id

        self.confirm_dialog = ConfirmationDialog(
            f"Delete video source with ID {vidsrc_id}?", on_yes=self._delete_camera
        )
        self.button = ui.button("Delete", on_click=self._on_click).classes("text-md text-[#cad3f5] bg-black rounded-xl")

    def _on_click(self, args: ClickEventArguments) -> None:
        self.confirm_dialog.open()

    async def _delete_camera(self, args: ClickEventArguments) -> None:
        await globals.video_source_manager_loaded.wait()
        await globals.video_source_manager_loaded_from_db.wait()

        await globals.video_source_manager.remove_video_source(self.vidsrc_id)
        ui.navigate.to("/cameras")


@router.page("/cameras/{id}")
async def camera_view_page(id: int) -> None:
    sentinel_server.ui.add_global_style()
    sentinel_server.ui.pages_shared()

    with ui.element("div").classes("w-full flex h-2/5"):
        with ui.element("div").classes("w-3/5 border-r-2 border-gray-200"):
            ui.label("Live Feed").classes("text-2xl font-bold text-[#4a4e69] pl-5")
            camera_view = CameraView(id)

        with ui.element("div").classes("w-2/5 pl-5"):
            ui.label("Camera details").classes("text-2xl font-bold text-[#4a4e69]")
            camera_details = CameraDetails(id)

    with ui.element("div").classes("w-full flex flex-col border-t-2 border-gray-200 pt-5"):
        ui.label("Logs").classes("text-2xl font-bold text-[#4a4e69] pl-5 pb-3")
        with ui.element("div").classes("flex justify-center w-full"):
            alert_table = AlertTable(source_id=id)

    with ui.element("div").classes("w-full flex justify-end px-5 pb-5"):
        delete_button = CameraDeleteButton(id)

    await ui.context.client.connected()
    await camera_view.start_capture()
    await camera_details.fill_info()
    await alert_table.refresh()
    await alert_table.register()

    await ui.context.client.disconnected()
    await camera_view.stop_capture()
    await alert_table.deregister()
