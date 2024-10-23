from nicegui import ui

from sentinel_server.ui.login import logout_user


def pages_shared():
    # TODO: How to make the drawer retain its open/closed state across pages?
    with ui.left_drawer(fixed=False, value=False).classes("shadow-2xl") as left_drawer:
        ui.button("Dashboard", on_click=lambda: ui.navigate.to("/dashboard"))
        ui.button("Cameras", on_click=lambda: ui.navigate.to("/cameras"))
        ui.button("Devices", on_click=lambda: ui.navigate.to("/devices"))
        ui.button("Alerts", on_click=lambda: ui.navigate.to("/alerts"))
        ui.button("Settings", on_click=lambda: ui.navigate.to("/settings"))

        ui.button("Logout", on_click=logout_user)

    with ui.header():
        ui.button(on_click=lambda: left_drawer.toggle(), icon="menu")
        ui.label("Sentinel")
