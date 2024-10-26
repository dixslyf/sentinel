from nicegui import ui, app

from sentinel_server.ui.login import logout_user

# Make this function global for modularity 
def add_global_style():
    # This line is to remove nicegui default padding
    ui.add_head_html('<style>body {background-color: FFFDD0; }</style>')
    ui.add_head_html("<style>.nicegui-content { padding: 0 !important; }</style>")


def pages_shared():
    # top nav bar 
    with ui.header().classes("bg-gray-800 justify-between items-center shadow-2xl"):
        ui.label("Sentinel").classes("text-2xl text-gray-200")

        with ui.element("div").classes("flex gap-2"):
            ui.label(f"{app.storage.user['username']}").classes("flex items-center text-xl text-gray-200")

            with ui.element("div").classes():
                with ui.button(on_click=logout_user).props("flat"):
                    ui.icon("logout").classes("text-gray-300")
    
    # left nav bar
    with ui.left_drawer(bottom_corner=True).classes("gap-10").style("background-color: #8525d9"):

        # ui.button("Dashboard", on_click=lambda: ui.navigate.to("/dashboard"))
        with ui.button(on_click=lambda: ui.navigate.to("/dashboard")).classes("flex items-start w-full").props("flat no-caps"):
            with ui.element("div").classes("flex items-center gap-3 text-xl text-gray-200"):
                ui.icon("dashboard")
                ui.label("Dashboard")

        # ui.button("Cameras", on_click=lambda: ui.navigate.to("/cameras"))
        with ui.button(on_click=lambda:ui.navigate.to("/cameras")).classes("flex items-start w-full").props("flat no-caps"):
            with ui.element("div").classes("flex items-center gap-3 text-xl text-gray-200"):
                ui.icon("camera_alt")
                ui.label("Cameras")

        # ui.button("Devices", on_click=lambda: ui.navigate.to("/devices"))
        with ui.button(on_click=lambda:ui.navigate.to("/devices")).classes("flex items-start w-full").props("flat no-caps"):
            with ui.element("div").classes("flex items-center gap-3 text-xl text-gray-200"):
                ui.icon("devices_other")
                ui.label("Devices")

        # ui.button("Alerts", on_click=lambda: ui.navigate.to("/alerts"))
        with ui.button(on_click=lambda:ui.navigate.to("/alerts")).classes("flex items-start w-full").props("flat no-caps"):
            with ui.element("div").classes("flex items-center gap-3 text-xl text-gray-200"):
                ui.icon("notification_important")
                ui.label("Alerts")

        # ui.button("Settings", on_click=lambda: ui.navigate.to("/settings"))
        with ui.button(on_click=lambda:ui.navigate.to("/settings")).classes("flex items-start w-full").props("flat no-caps"):
            with ui.element("div").classes("flex items-center gap-3 text-xl text-gray-200"):
                ui.icon("settings")
                ui.label("Setting")
