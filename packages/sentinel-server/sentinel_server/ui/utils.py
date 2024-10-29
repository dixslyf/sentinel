from typing import Callable, Optional

from nicegui import ui
from nicegui.events import ClickEventArguments


class ConfirmationDialog:
    """
    Represents a dialog for confirming a user action with either "Yes" or "No".
    """

    def __init__(
        self,
        body: str,
        header: str = "Confirmation",
        on_no: Optional[Callable[[ClickEventArguments], None]] = None,
        on_yes: Optional[Callable[[ClickEventArguments], None]] = None,
    ) -> None:
        """
        Initialises the confirmation dialog.

        Parameters:
            body (str): The main message displayed in the dialog.
            header (str): The header/title of the dialog, by default "Confirmation".
            on_no (Optional[Callable[[nicegui.elements.button.Button], None]]):
                A callback function to execute when the "No" button is clicked, by default None.
                Note that the dialog will always close when "No" is clicked.
            on_yes (Optional[Callable[[nicegui.elements.button.Button], None]]):
                A callback function to execute when the "Yes" button is clicked, by default None.
                Note that the dialog will always close when "Yes" is clicked.
        """
        self.dialog = ui.dialog()

        def on_no_wrapper(args: ClickEventArguments) -> None:
            if on_no is not None:
                on_no(args)
            self.close()

        def on_yes_wrapper(args: ClickEventArguments) -> None:
            if on_yes is not None:
                on_yes(args)
            self.close()

        with self.dialog, ui.card():
            ui.markdown(f"**{header}**")

            ui.markdown(f"{body}")

            # Name of the video source.
            with ui.grid(columns=2):
                ui.button("No", on_click=on_no_wrapper)
                ui.button("Yes", on_click=on_yes_wrapper)

    def open(self) -> None:
        self.dialog.open()

    def close(self) -> None:
        self.dialog.close()
