import asyncio
import enum
from enum import StrEnum
from typing import Any, Optional, Protocol

from aioreactive import AsyncDisposable, AsyncObservable, AsyncObserver, AsyncSubject


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


class ReactiveSubscriber(AsyncObserver[Alert]):
    """
    A subscriber that receives alert notifications.
    """

    def __init__(self, raw_sub: Subscriber):
        self._raw_sub = raw_sub

    async def asend(self, alert: Alert):
        await self._raw_sub.notify(alert)

    async def athrow(self, ex: Exception):
        alert = ExceptionAlert(ex)
        await self._raw_sub.notify(alert)

    async def aclose(self):
        pass


class Emitter(Protocol):
    """
    An emitter that generates alert notifications.
    """

    async def next_alert(self) -> Alert:
        """
        Emit an alert.
        """


class ReactiveEmitter(AsyncObservable[Alert]):
    """
    An emitter that generates alert notifications.
    """

    def __init__(self, raw_emitter: Emitter):
        self._raw_emitter: Emitter = raw_emitter
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


class AlertManager:
    def __init__(self) -> None:
        self._emitters: dict[Emitter, ReactiveEmitter] = {}
        self._subscribers: dict[Subscriber, ReactiveSubscriber] = {}
        self._subscriptions: dict[tuple[Subscriber, Emitter], AsyncDisposable] = {}

    async def subscribe(self, raw_subscriber: Subscriber, raw_emitter: Emitter) -> bool:
        # Subscription already exists.
        if (raw_subscriber, raw_emitter) in self._subscriptions:
            return False

        # At this point, the subscription doesn't exist yet.

        self._register_subscriber(raw_subscriber)
        self._register_emitter(raw_emitter)

        subscriber = self._subscribers[raw_subscriber]
        emitter = self._emitters[raw_emitter]

        subscription = await emitter.subscribe_async(subscriber)
        self._subscriptions[(raw_subscriber, raw_emitter)] = subscription
        return True

    async def unsubscribe(
        self, raw_subscriber: Subscriber, raw_emitter: Emitter
    ) -> bool:
        if (raw_subscriber, raw_emitter) in self._subscriptions:
            subscription = self._subscriptions[(raw_subscriber, raw_emitter)]
            await subscription.dispose_async()
            return True

        # No existing subscription.
        return False

    async def start(self) -> None:
        emitters = (emitter.start() for emitter in self._emitters.values())
        await asyncio.gather(*emitters)

    def _register_emitter(self, raw_emitter: Emitter) -> bool:
        if raw_emitter in self._emitters:
            return False
        self._emitters[raw_emitter] = ReactiveEmitter(raw_emitter)
        return True

    def _register_subscriber(self, raw_subscriber: Subscriber) -> bool:
        if raw_subscriber in self._subscribers:
            return False
        self._subscribers[raw_subscriber] = ReactiveSubscriber(raw_subscriber)
        return True
