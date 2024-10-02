import enum
from enum import StrEnum
from typing import Any, Optional, Protocol

from aioreactive import AsyncObservable, AsyncObserver


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


class Subscriber(AsyncObserver[Alert]):
    """
    A subscriber that receives alert notifications.
    """


class Emitter(AsyncObservable[Alert]):
    """
    A source that emits alerts.
    """
