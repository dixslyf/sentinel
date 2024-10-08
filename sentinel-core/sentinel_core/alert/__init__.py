import enum
from enum import StrEnum
from typing import Any, Optional, Protocol


class ThreatLevel(StrEnum):
    Unknown = enum.auto()
    Safe = enum.auto()
    Warning = enum.auto()


class Alert(Protocol):
    @property
    def header(self) -> str:
        """
        Returns the alert's header.
        """

    @property
    def description(self) -> str:
        """
        Returns a description of the alert.
        """

    @property
    def threat_level(self) -> ThreatLevel:
        """
        Returns the alert's threat level.
        """

    @property
    def data(self) -> Optional[dict[str, Any]]:
        """
        Returns additional data associated with the alert.
        """


class ExceptionAlert(Alert):
    def __init__(self, ex: Exception):
        self._ex = ex

    @property
    def header(self) -> str:
        return "Sentinel Error"

    @property
    def description(self) -> str:
        return f"An error occurred: '{self._ex}'"

    @property
    def threat_level(self) -> ThreatLevel:
        return ThreatLevel.Unknown

    @property
    def data(self) -> Optional[dict[str, Any]]:
        return {
            "exception": self._ex,
        }


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
