import dataclasses
from typing import Protocol


@dataclasses.dataclass
class Alert:
    header: str
    description: str
    source: str


class Subscriber(Protocol):
    """
    A subscriber that receives alert notifications.
    """

    async def notify(self, alert: Alert):
        """
        Receive an alert notification.
        """


class Emitter(Protocol):
    """
    An emitter that generates alert notifications.
    """

    async def next_alert(self) -> Alert:
        """
        Emit an alert.
        """
