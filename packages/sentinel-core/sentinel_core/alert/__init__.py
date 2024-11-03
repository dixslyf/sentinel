from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from dataclasses_json import dataclass_json


@dataclass_json
@dataclass
class Alert:
    header: str
    description: str
    source: str
    timestamp: datetime


class AsyncSubscriber(Protocol):
    """
    A subscriber that receives alert notifications asynchronously.
    """

    async def notify(self, alert: Alert) -> None:
        """
        Receive an alert notification.
        """

    async def clean_up(self) -> None:
        """
        Clean up any resources associated with the subscriber.
        """
        return


class SyncSubscriber(Protocol):
    """
    A subscriber that receives alert notifications synchronously.
    """

    def notify(self, alert: Alert) -> None:
        """
        Receive an alert notification.
        """

    def clean_up(self) -> None:
        """
        Clean up any resources associated with the subscriber.
        """
        pass


class Emitter(Protocol):
    """
    An emitter that generates alert notifications.
    """

    async def next_alert(self) -> Alert:
        """
        Emit an alert.
        """
