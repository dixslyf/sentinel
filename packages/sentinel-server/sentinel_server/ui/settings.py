import logging
import os

import nicegui
from nicegui import APIRouter, app, ui

import sentinel_server.auth
import sentinel_server.ui
from sentinel_server.ui.login import logout_user
from sentinel_server.ui.utils import ConfirmationDialog

logger = logging.getLogger(__name__)

router = APIRouter()


class AuthenticationSection:
    def __init__(self):
        auth_card = ui.card()
        with auth_card:
            ui.label("Authentication")

            # Username section
            ui.label("Username")
            self.username_input = ui.input(
                label="Username",
                value=app.storage.user["username"],
                validation={"Username cannot be empty": lambda value: len(value) > 0},
            )

            self.username_update_button = ui.button(
                "Update", on_click=self.username_update_button_on_click
            )

            # Password section
            ui.label("Change Password")
            self.password_input = ui.input(
                label="New Password",
                password=True,
                password_toggle_button=True,
                validation={"Password cannot be empty": lambda value: len(value) > 0},
            )

            self.password_confirm_input = ui.input(
                label="Confirm New Password",
                password=True,
                password_toggle_button=True,
                validation={
                    "Passwords do not match": lambda value: value
                    == self.password_input.value
                },
            ).without_auto_validation()

            self.password_update_button = ui.button(
                "Update", on_click=self.password_update_button_on_click
            )

    async def username_update_button_on_click(
        self, button: nicegui.elements.button.Button
    ):
        if not self.username_input.validate():
            return

        user_id = app.storage.user["user_id"]
        await sentinel_server.auth.update_username(user_id, self.username_input.value)
        app.storage.user["username"] = self.username_input.value

        ui.notify("Updated username!")

    async def password_update_button_on_click(
        self, button: nicegui.elements.button.Button
    ):
        if (
            not self.password_input.validate()
            or not self.password_confirm_input.validate()
        ):
            return

        user_id = app.storage.user["user_id"]
        await sentinel_server.auth.update_password(user_id, self.password_input.value)

        ui.notify("Updated password!")


class SystemSection:
    def __init__(self) -> None:
        restart_confirm_dialog = ConfirmationDialog(
            "Restart Sentinel?",
            on_yes=self._restart,
        )

        shutdown_confirm_dialog = ConfirmationDialog(
            "Shut down Sentinel?",
            on_yes=lambda _: app.shutdown(),
        )

        system_card = ui.card()
        with system_card:
            ui.label("System")

            with ui.grid(columns=2):
                ui.button("Restart", on_click=restart_confirm_dialog.open)
                ui.button("Shutdown", on_click=shutdown_confirm_dialog.open)

    def _restart(self, button: nicegui.elements.button.Button) -> None:
        # Log the user out.
        logout_user()

        # As suggested by:
        # https://github.com/zauberzeug/nicegui/discussions/1719#discussioncomment-7159050.
        # Assumes `ui.run(..., reload=True)`.
        os.utime(__file__)


@router.page("/settings")
def settings():
    sentinel_server.ui.pages_shared()
    ui.label("settings")

    AuthenticationSection()

    SystemSection()
