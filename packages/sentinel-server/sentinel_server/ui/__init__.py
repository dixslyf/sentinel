from nicegui import ui

from sentinel_server.ui.login import logout_user

# Make this function global for modularity 
def add_global_style():
    # This line is to remove nicegui default padding
    ui.add_head_html("<style>.nicegui-content { padding: 0 !important; }</style>")


def pages_shared():
    # TODO: How to make the drawer retain its open/closed state across pages?

    #TODO
    # left nav bar 
    
    # top nav bar 
    with ui.element("div").classes("border-2 w-screen h-16 flex justify-between"):

        ui.label("Sentinel Icon Here").classes("flex item-center text-2xl")
        
        with ui.element("div").classes("flex gap-2 space-x-8 space-x-reverse"):
            # TODO 
            # here should grab username and place into the label
            ui.label("username here").classes("flex items-center text-xl text-gray-500")

            with ui.element("div").classes("flex items-center"):
                with ui.button(on_click=logout_user).classes("h-10 w-12 text-xl").props('flat'):
                    ui.icon("logout").classes("text-gray-400")
            