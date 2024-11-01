from dataclasses import dataclass
from typing import Protocol

from dataclasses_json import dataclass_json


@dataclass_json
@dataclass
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
