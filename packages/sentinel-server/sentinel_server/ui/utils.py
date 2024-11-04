import asyncio
from typing import Awaitable, Callable, Optional

from nicegui import run, ui
from nicegui.events import ClickEventArguments


class ConfirmationDialog:
    """
    Represents a dialog for confirming a user action with either "Yes" or "No".
    """

    def __init__(
        self,
        body: str,
        header: str = "Confirmation",
        on_no: Optional[Callable[[ClickEventArguments], None | Awaitable[None]]] = None,
        on_yes: Optional[
            Callable[[ClickEventArguments], None | Awaitable[None]]
        ] = None,
    ) -> None:
        """
        Initialises the confirmation dialog.

        Parameters:
            body (str): The main message displayed in the dialog.
            header (str): The header/title of the dialog, by default "Confirmation".
            on_no (Optional[Callable[[ClickEventArguments], None | Awaitable[None]]]):
                A callback function to execute when the "No" button is clicked, by default None.
                Note that the dialog will always close when "No" is clicked.
            on_yes (Optional[Callable[[ClickEventArguments], None | Awaitable[None]]]):
                A callback function to execute when the "Yes" button is clicked, by default None.
                Note that the dialog will always close when "Yes" is clicked.
        """
        self.dialog = ui.dialog()

        async def on_no_wrapper(args: ClickEventArguments) -> None:
            self.close()
            if on_no is not None:
                if asyncio.iscoroutinefunction(on_no):
                    await on_no(args)
                else:
                    await run.io_bound(on_no, args)

        async def on_yes_wrapper(args: ClickEventArguments) -> None:
            self.close()
            if on_yes is not None:
                if asyncio.iscoroutinefunction(on_yes):
                    await on_yes(args)
                else:
                    await run.io_bound(on_yes, args)

        with self.dialog, ui.card().classes("w-2/12 h-1/3 gap-8"):
            ui.markdown(f"**{header}**").classes(
                "text-2xl text-[#4a4e69] font-bold w-full text-center"
            )

            ui.markdown(f"{body}").classes("w-full text-xl text-[#4a4e69] text-center")

            # Name of the video source.
            with ui.grid(columns=2).classes("w-full"):
                ui.button("No", on_click=on_no_wrapper).classes(
                    "text-md text-[#cad3f5] bg-black rounded-xl hover:bg-gray-500"
                ).props("no-caps")
                ui.button("Yes", on_click=on_yes_wrapper).classes(
                    "text-md text-[#cad3f5] bg-black rounded-xl hover:bg-gray-500"
                ).props("no-caps")

    def open(self) -> None:
        self.dialog.open()

    def close(self) -> None:
        self.dialog.close()
