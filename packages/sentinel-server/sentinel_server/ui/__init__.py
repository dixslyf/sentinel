from typing import Any, Callable

from nicegui import app, ui
from nicegui.elements.button import Button
from nicegui.events import ClickEventArguments

from sentinel_server.ui.login import logout_user


class SharedPageLayout:
    CONTAINER_PADDING: int = 8

    def __init__(self, page_header: str) -> None:
        self._page_header: str = page_header
        self._setup_view()
        self._setup_controls()

    def _setup_view(self) -> None:
        # Remove NiceGui's default padding.
        ui.add_head_html("<style>body {background-color: FFFDD0; }</style>")
        ui.add_head_html("<style>.nicegui-content { padding: 0 !important; }</style>")

        self._setup_navbar()
        self._setup_drawer()
        self._setup_main_container()

    def _setup_navbar(self) -> None:
        with ui.header().classes(
            "bg-[#24273a] justify-between items-center shadow-2xl"
        ):
            # Sentinel icon and page header.
            with ui.element("div").classes("flex items-center gap-6 pl-3"):
                ui.image("sentinel_server/ui/static/sentinel_logo.png").classes(
                    "h-18 w-16"
                )
                ui.label(self._page_header).classes(
                    "text-3xl font-[500] text-[#cad3f5]"
                )

            # Username and logout icon.
            with ui.element("div").classes("flex items-center gap-2"):
                ui.label(f"{app.storage.user['username']}").classes(
                    "flex items-center text-xl text-[#cad3f5]"
                )

                self._logout_button = ui.button().props("flat")
                with self._logout_button:
                    ui.icon("logout").classes("text-[#cad3f5]")

    def _setup_drawer(self) -> None:
        labels_icons: dict[str, str] = {
            "Dashboard": "dashboard",
            "Cameras": "camera_alt",
            "Devices": "devices_other",
            "Alerts": "notification_important",
            "Settings": "settings",
        }

        with ui.left_drawer(bottom_corner=True).classes("gap-10").style(
            "background-color: #5b6078"
        ):
            self._buttons: dict[str, Button] = {
                label: SharedPageLayout._make_navbar_button(label, icon)
                for label, icon in labels_icons.items()
            }

    def _setup_main_container(self) -> None:
        self._main_container = ui.element("div").classes(
            f"w-full p-{SharedPageLayout.CONTAINER_PADDING} flex flex-col"
        )

    def _setup_controls(self) -> None:
        self._logout_button.on_click(logout_user)
        for label, button in self._buttons.items():
            button.on_click(SharedPageLayout._make_navigation_function(label))

    @staticmethod
    def _make_navbar_button(label: str, icon: str) -> Button:
        button_classes: str = "flex items-start w-full"
        button_props: str = "flat no-caps"

        button = ui.button().classes(button_classes).props(button_props)

        with button:
            with ui.element("div").classes(
                "flex items-center gap-3 text-xl text-[#cad3f5]"
            ):
                ui.icon(icon)
                ui.label(label)

        return button

    @staticmethod
    def _make_navigation_function(label: str) -> Callable[[ClickEventArguments], Any]:
        return lambda args: ui.navigate.to(f"/{label.lower()}")

    def __enter__(self):
        self._main_container.__enter__()

    def __exit__(self, *args):
        self._main_container.__exit__(*args)


# Make this function global for modularity
def add_global_style():
    # This line is to remove nicegui default padding
    ui.add_head_html("<style>body {background-color: FFFDD0; }</style>")
    ui.add_head_html("<style>.nicegui-content { padding: 0 !important; }</style>")


def pages_shared():
    # top nav bar
    with ui.header().classes("bg-[#24273a] justify-between items-center shadow-2xl"):
        # ui.label("Sentinel").classes("text-2xl text-gray-200")
        ui.image("sentinel_server/ui/static/sentinel_logo.png").classes("h-18 w-16")

        with ui.element("div").classes("flex gap-2"):
            ui.label(f"{app.storage.user['username']}").classes(
                "flex items-center text-xl text-[#cad3f5]"
            )

            with ui.element("div").classes():
                with ui.button(on_click=logout_user).props("flat"):
                    ui.icon("logout").classes("text-[#cad3f5]")

    # left nav bar
    with ui.left_drawer(bottom_corner=True).classes("gap-10").style(
        "background-color: #5b6078"
    ):

        # ui.button("Dashboard", on_click=lambda: ui.navigate.to("/dashboard"))
        with ui.button(on_click=lambda: ui.navigate.to("/dashboard")).classes(
            "flex items-start w-full"
        ).props("flat no-caps"):
            with ui.element("div").classes(
                "flex items-center gap-3 text-xl text-[#cad3f5]"
            ):
                ui.icon("dashboard")
                ui.label("Dashboard")

        # ui.button("Cameras", on_click=lambda: ui.navigate.to("/cameras"))
        with ui.button(on_click=lambda: ui.navigate.to("/cameras")).classes(
            "flex items-start w-full"
        ).props("flat no-caps"):
            with ui.element("div").classes(
                "flex items-center gap-3 text-xl text-[#cad3f5]"
            ):
                ui.icon("camera_alt")
                ui.label("Cameras")

        # ui.button("Devices", on_click=lambda: ui.navigate.to("/devices"))
        with ui.button(on_click=lambda: ui.navigate.to("/devices")).classes(
            "flex items-start w-full"
        ).props("flat no-caps"):
            with ui.element("div").classes(
                "flex items-center gap-3 text-xl text-[#cad3f5]"
            ):
                ui.icon("devices_other")
                ui.label("Devices")

        # ui.button("Alerts", on_click=lambda: ui.navigate.to("/alerts"))
        with ui.button(on_click=lambda: ui.navigate.to("/alerts")).classes(
            "flex items-start w-full"
        ).props("flat no-caps"):
            with ui.element("div").classes(
                "flex items-center gap-3 text-xl text-[#cad3f5]"
            ):
                ui.icon("notification_important")
                ui.label("Alerts")

        # ui.button("Settings", on_click=lambda: ui.navigate.to("/settings"))
        with ui.button(on_click=lambda: ui.navigate.to("/settings")).classes(
            "flex items-start w-full"
        ).props("flat no-caps"):
            with ui.element("div").classes(
                "flex items-center gap-3 text-xl text-[#cad3f5]"
            ):
                ui.icon("settings")
                ui.label("Settings")
