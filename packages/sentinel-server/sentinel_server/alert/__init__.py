import asyncio
import logging
from typing import Optional, Self

from aioreactive import AsyncDisposable, AsyncObservable, AsyncObserver, AsyncSubject
from sentinel_core.alert import Alert, Emitter, Subscriber

logger = logging.getLogger(__name__)


class ReactiveSubscriber(AsyncObserver[Alert]):
    """
    A subscriber that receives alert notifications.
    """

    def __init__(self, raw_sub: Subscriber):
        self._raw_sub = raw_sub

    async def asend(self, alert: Alert):
        await self._raw_sub.notify(alert)

    async def athrow(self, ex: Exception):
        alert = Alert("Sentinel Error", f"An error occurred: {str(ex)}", "Unknown")
        await self._raw_sub.notify(alert)

    async def aclose(self):
        pass

    @property
    def raw_subscriber(self) -> Subscriber:
        return self._raw_sub


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

    @property
    def raw_emitter(self) -> Emitter:
        return self._raw_emitter


class DatabaseSubscriber(Subscriber):
    def __init__(self) -> None:
        pass

    async def notify(self, alert: Alert):
        # TODO: replace with database implementation
        logger.info(f"{alert.header}\n{alert.description}\n{alert.source}")


class AlertManager:
    def __init__(self) -> None:
        self._emitters: dict[ReactiveEmitter, Optional[asyncio.Task]] = {}
        self._subscribers: list[ReactiveSubscriber] = []
        self._subscriptions: dict[
            tuple[ReactiveEmitter, ReactiveSubscriber], AsyncDisposable
        ] = {}

    @classmethod
    async def create(cls) -> Self:
        self = cls()
        await self.add_subscriber(DatabaseSubscriber())
        return self

    async def add_emitter(self, raw_emitter: Emitter) -> None:
        assert all(
            raw_emitter is not emitter.raw_emitter for emitter in self._emitters.keys()
        )

        emitter = ReactiveEmitter(raw_emitter)

        # Subscribe all existing subscribers to the emitter.
        for subscriber in self._subscribers:
            sub = await emitter.subscribe_async(subscriber)
            self._subscriptions[(emitter, subscriber)] = sub

        self._start_emitter(emitter)

    async def add_subscriber(self, raw_subscriber: Subscriber) -> None:
        assert all(
            raw_subscriber is not subscriber.raw_subscriber
            for subscriber in self._subscribers
        )

        subscriber = ReactiveSubscriber(raw_subscriber)
        self._subscribers.append(subscriber)

        # Subscribe the subscriber to all emitters.
        for emitter in self._emitters.keys():
            sub = await emitter.subscribe_async(subscriber)
            self._subscriptions[(emitter, subscriber)] = sub

    async def remove_emitter(self, raw_emitter: Emitter) -> bool:
        emitter = next(
            (
                emitter
                for emitter in self._emitters.keys()
                if emitter.raw_emitter is raw_emitter
            ),
            None,
        )

        if emitter is None:
            return False

        self._stop_emitter(emitter)
        del self._emitters[emitter]

        return True

    async def remove_subscriber(self, raw_subscriber: Subscriber) -> bool:
        subscriber = next(
            (
                subscriber
                for subscriber in self._subscribers
                if subscriber.raw_subscriber is raw_subscriber
            ),
            None,
        )

        if subscriber is None:
            return False

        # Remove all relevant subscriptions.
        keys_to_remove: list[tuple[ReactiveEmitter, ReactiveSubscriber]] = []
        for (emitter, subscr), sub in self._subscriptions.items():
            if subscr is subscriber:
                await sub.dispose_async()
            keys_to_remove.append((emitter, subscr))

        for key in keys_to_remove:
            del self._subscriptions[key]

        self._subscribers.remove(subscriber)

        return True

    def _start_emitter(self, emitter: ReactiveEmitter):
        async def emitter_task() -> None:
            try:
                await emitter.start()
            except asyncio.CancelledError:  # For stopping the emitter.
                await emitter.stop()
                self._emitters[emitter] = None

                # Remove all relevant subscriptions.
                keys_to_remove: list[tuple[ReactiveEmitter, ReactiveSubscriber]] = []
                for (em, subscriber), sub in self._subscriptions.items():
                    if em is emitter:
                        await sub.dispose_async()
                    keys_to_remove.append((em, subscriber))

                for key in keys_to_remove:
                    del self._subscriptions[key]

        task = asyncio.create_task(emitter_task())
        self._emitters[emitter] = task

    def _stop_emitter(self, emitter: ReactiveEmitter) -> bool:
        task = self._emitters[emitter]
        if task is not None:
            task.cancel()
            return True
        return False
