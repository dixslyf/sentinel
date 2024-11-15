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
        background: bool = True,
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
        self.background: bool = background

        async def on_no_wrapper(args: ClickEventArguments) -> None:
            if self.background:
                self.close()
            else:
                self._hide_prompt()
                self._show_loading()

            if on_no is not None:
                if asyncio.iscoroutinefunction(on_no):
                    await on_no(args)
                elif self.background:
                    await run.io_bound(on_no, args)
                else:
                    on_no(args)

            if not self.background:
                self.close()

        async def on_yes_wrapper(args: ClickEventArguments) -> None:
            if self.background:
                self.close()
            else:
                self._hide_prompt()
                self._show_loading()

            if on_yes is not None:
                if asyncio.iscoroutinefunction(on_yes):
                    await on_yes(args)
                elif self.background:
                    await run.io_bound(on_yes, args)
                else:
                    on_yes(args)

            if not self.background:
                self.close()

        with self.dialog:
            self.prompt_card = ui.card().classes("w-2/12 h-1/3 gap-8")
            with self.prompt_card:
                ui.markdown(f"**{header}**").classes(
                    "text-2xl text-[#4a4e69] font-bold w-full text-center"
                )

                ui.markdown(f"{body}").classes(
                    "w-full text-xl text-[#4a4e69] text-center"
                )

                with ui.grid(columns=2).classes("w-full"):
                    ui.button("No", on_click=on_no_wrapper).classes(
                        "text-md text-[#cad3f5] bg-black rounded-xl hover:bg-gray-500"
                    ).props("no-caps")
                    ui.button("Yes", on_click=on_yes_wrapper).classes(
                        "text-md text-[#cad3f5] bg-black rounded-xl hover:bg-gray-500"
                    ).props("no-caps")

            self.loading_card = ui.card().classes(
                "w-2/12 h-1/3 gap-8 flex items-center justify-center"
            )
            with self.loading_card:
                ui.spinner(size="md")

    def open(self) -> None:
        self._show_prompt()
        self._hide_loading()
        self.dialog.open()

    def close(self) -> None:
        self.dialog.close()

    def _show_prompt(self) -> None:
        self.prompt_card.set_visibility(True)

    def _hide_prompt(self) -> None:
        self.prompt_card.set_visibility(False)

    def _show_loading(self) -> None:
        self.loading_card.set_visibility(True)

    def _hide_loading(self) -> None:
        self.loading_card.set_visibility(False)
