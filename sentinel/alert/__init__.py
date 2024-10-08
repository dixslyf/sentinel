import enum
from enum import StrEnum
from typing import Any, Optional, Protocol

from aioreactive import AsyncObservable, AsyncObserver, AsyncSubject


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


class RawSubscriber(Protocol):
    """
    A subscriber that receives alert notifications.
    """

    async def notify(self, alert: Alert):
        """
        Receive an alert notification.
        """


class Subscriber(AsyncObserver[Alert]):
    """
    A subscriber that receives alert notifications.
    """

    def __init__(self, raw_sub: RawSubscriber):
        self._raw_sub = raw_sub

    async def asend(self, alert: Alert):
        await self._raw_sub.notify(alert)

    async def athrow(self, ex: Exception):
        alert = ExceptionAlert(ex)
        await self._raw_sub.notify(alert)

    async def aclose(self):
        pass


class RawEmitter(Protocol):
    """
    An emitter that generates alert notifications.
    """

    async def next_alert(self) -> Alert:
        """
        Emit an alert.
        """


class Emitter(AsyncObservable[Alert]):
    """
    An emitter that generates alert notifications.
    """

    def __init__(self, raw_emitter: RawEmitter):
        self._raw_emitter: RawEmitter = raw_emitter
        self._subject_out: AsyncSubject = AsyncSubject()
        self._run: bool = False

    async def subscribe_async(self, observer):
        return await self._subject_out.subscribe_async(observer)

    async def start(self) -> None:
        self._run = True
        while self._run:
            alert: Alert = await self._raw_emitter.next_alert()
            await self._subject_out.asend(alert)

    def pause(self) -> None:
        self._run = False

    async def stop(self) -> None:
        self.pause()
        await self._subject_out.aclose()
