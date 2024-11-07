from typing import Any, Callable, Self

from nicegui import app, ui
from nicegui.elements.button import Button
from nicegui.events import ClickEventArguments

from sentinel_server.ui.login import logout_user


def add_global_style():
    # Remove NiceGui default padding.
    ui.add_head_html("<style>body {background-color: FFFDD0; }</style>")
    ui.add_head_html("<style>.nicegui-content { padding: 0 !important; }</style>")


class SharedPageLayout:
    CONTAINER_PADDING: int = 8

    def __init__(self, page_header: str) -> None:
        self._page_header: str = page_header
        self._setup_view()
        self._setup_controls()

    def refresh(self) -> None:
        self._username_label.set_text(f"{app.storage.user['username']}")

    def _setup_view(self) -> None:
        add_global_style()

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
                self._username_label = ui.label(
                    f"{app.storage.user['username']}"
                ).classes("flex items-center text-xl text-[#cad3f5]")

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
                label: SharedPageLayout._make_navbar_button(
                    label, icon, self._page_header
                )
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
    def _make_navbar_button(label: str, icon: str, page_header: str) -> Button:
        button_classes: str = "flex items-start w-full"
        button_props: str = "flat no-caps"

        if label.lower() == page_header.lower():
            button_classes += " bg-[#727894]"

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

    def __enter__(self) -> Self:
        self._main_container.__enter__()
        return self

    def __exit__(self, *args):
        self._main_container.__exit__(*args)
