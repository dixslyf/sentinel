import logging
from typing import Optional

from fastapi import Request
from fastapi.responses import RedirectResponse
from nicegui import APIRouter, app, ui
from starlette.middleware.base import BaseHTTPMiddleware

import sentinel_server.auth
import sentinel_server.config
import sentinel_server.ui

UNRESTRICTED_PAGE_ROUTES: set[str] = {"/", "/login"}

router = APIRouter()


class AuthenticationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not app.storage.user.get("authenticated", False):
            if (
                not request.url.path.startswith("/_nicegui")
                and not request.url.path.startswith("/_static")
                and request.url.path not in UNRESTRICTED_PAGE_ROUTES
            ):
                app.storage.user["referrer_path"] = request.url.path
                return RedirectResponse("/login")
        return await call_next(request)


# Main login page.
@router.page("/login")
def login_page() -> Optional[RedirectResponse]:
    sentinel_server.ui.add_global_style()

    if app.storage.user.get("authenticated", False):
        return RedirectResponse("/dashboard")

    with ui.element("div").classes("w-screen h-screen flex m-0"):
        # left side of the page
        with ui.element("div").classes(
            "w-1/2 border-2 flex justify-between bg-[#24273a]"
        ):
            with ui.element("div").classes(
                "w-full flex gap-10 items-center justify-center"
            ):
                ui.image("sentinel_server/ui/static/sentinel_logo.png").classes(
                    "h-[6.5rem] w-24"
                )

                with ui.element("div").classes("flex gap-10 flex-col gap-3"):
                    ui.label("Welcome!").classes(
                        "text-4xl font-extrabold text-[#cad3f5]"
                    )
                    ui.label("Sentinel: Smart Home Security and Alert System").classes(
                        "text-xl text-[#c6a0f6]"
                    )

        # right side
        with ui.element("div").classes("w-1/2 flex justify-start text-center m-auto"):
            login_form()

    return None


# Login form component.
def login_form() -> Optional[RedirectResponse]:
    if app.storage.user.get("authenticated", False):
        return RedirectResponse("/dashboard")

    # main styling for login form
    with ui.element("div").classes("space-y-4 w-2/5 ml-16"):
        ui.label("Sign In").classes("font-semibold text-4xl text-left font-serif")

        username_input = ui.input(label="Username")
        password_input = ui.input(
            label="Password", password=True, password_toggle_button=True
        )

        with ui.element("div").classes("flex justify-end"):
            login_button = ui.button("Log In").classes(
                "text-lg text-white bg-black rounded-xl py-1 px-3"
            )

    # validation for login data
    async def try_login() -> None:
        logging.info(f"Checking login credentials for: {username_input.value}")

        db_user: Optional[sentinel_server.models.User] = (
            await sentinel_server.models.User.get_or_none(username=username_input.value)
        )

        if not db_user or not sentinel_server.auth.verify_password(
            password_input.value, db_user.hashed_password
        ):
            logging.info(f"Authentication failed for: {username_input.value}")
            ui.notify("Wrong username or password", color="negative")
            return None

        logging.info(f"Authentication succeeded for: {username_input.value}")
        app.storage.user.update(
            {
                "user_id": db_user.id,
                "username": username_input.value,
                "authenticated": True,
            }
        )
        ui.navigate.to(app.storage.user.get("referrer_path", "/"))

    username_input.on("keydown.enter", try_login)
    password_input.on("keydown.enter", try_login)
    login_button.on_click(try_login)

    return None


def logout_user() -> None:
    app.storage.user.update({"authenticated": False})
    logging.info("User logged out")
    ui.navigate.to("/login")
