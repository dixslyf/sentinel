import typing
from typing import Optional

import aiohttp
from sentinel_core.alert import Alert, AsyncSubscriber
from sentinel_core.plugins import (
    ComponentArgDescriptor,
    ComponentDescriptor,
    ComponentKind,
    Plugin,
)


class WebSocketSubscriber(AsyncSubscriber):
    """
    A subscriber that sends alerts over a WebSocket connection.
    """

    def __init__(self, websocket_url: str) -> None:
        self.websocket_url: str = websocket_url
        self.session: aiohttp.ClientSession = aiohttp.ClientSession()
        self.websocket: Optional[aiohttp.ClientWebSocketResponse] = None

    async def notify(self, alert: Alert) -> None:
        """Sends alert data over the WebSocket."""
        if self.websocket is None:
            self.websocket = await self.session.ws_connect(self.websocket_url)

        if self.websocket.closed:
            raise RuntimeError("WebSocket closed")

        # `self.connect() ensures that `self.websocket` is not `None`.
        self.websocket = typing.cast(aiohttp.ClientWebSocketResponse, self.websocket)
        await self.websocket.send_str(alert.to_json())

    async def clean_up(self) -> None:
        """Closes the WebSocket connection and session."""
        if self.websocket is not None:
            await self.websocket.close()

        await self.session.close()


_component_descriptor = ComponentDescriptor(
    display_name="WebSocket Alert Subscriber",
    kind=ComponentKind.AsyncSubscriber,
    cls=WebSocketSubscriber,
    args=(
        ComponentArgDescriptor(
            display_name="WebSocket URL",
            arg_name="websocket_url",
            option_type=str,
            required=True,
        ),
    ),
)

plugin = Plugin(frozenset({_component_descriptor}))
