import asyncio
import logging
import typing
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Optional, Self

from aioreactive import AsyncDisposable, AsyncObservable, AsyncObserver, AsyncSubject
from sentinel_core.alert import Alert, AsyncSubscriber, Emitter, SyncSubscriber
from sentinel_core.plugins import ComponentDescriptor, ComponentKind

import sentinel_server.tasks
from sentinel_server.models import Subscriber as DbSubscriber
from sentinel_server.plugins import PluginDescriptor, PluginManager

logger = logging.getLogger(__name__)


class AsyncSubscriberWrapper(AsyncSubscriber):
    """
    A wrapper around a synchronous subscriber to make it asynchronous.
    """

    def __init__(self, sync_subscriber: SyncSubscriber):
        self._sync_subscriber: SyncSubscriber = sync_subscriber

    async def notify(self, alert: Alert) -> None:
        return await sentinel_server.tasks.run_in_thread(
            self._sync_subscriber.notify, alert
        )

    async def clean_up(self) -> None:
        await sentinel_server.tasks.run_in_thread(self._sync_subscriber.clean_up)

    @property
    def wrapped(self) -> SyncSubscriber:
        return self._sync_subscriber


class ReactiveSubscriber(AsyncObserver[Alert]):
    """
    A subscriber that receives alert notifications.
    """

    def __init__(self, raw_sub: AsyncSubscriber):
        self._raw_sub: AsyncSubscriber = raw_sub

    @classmethod
    def from_sync(cls, raw_sync_sub: SyncSubscriber) -> Self:
        raw_async_sub = AsyncSubscriberWrapper(raw_sync_sub)
        return cls(raw_async_sub)

    async def asend(self, alert: Alert):
        await self._raw_sub.notify(alert)

    async def athrow(self, ex: Exception):
        alert = Alert(
            "Sentinel Error", f"An error occurred: {str(ex)}", "Unknown", datetime.now()
        )
        await self._raw_sub.notify(alert)

    async def aclose(self):
        pass

    @property
    def raw_subscriber(self) -> AsyncSubscriber:
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


class DatabaseSubscriber(AsyncSubscriber):
    def __init__(self) -> None:
        pass

    async def notify(self, alert: Alert):
        # TODO: replace with database implementation
        logger.info(f"{alert.header}\n{alert.description}\n{alert.source}")


class SubscriptionRegistrar:
    def __init__(self) -> None:
        self._emitters: dict[ReactiveEmitter, Optional[asyncio.Task]] = {}
        self._subscribers: list[ReactiveSubscriber] = []
        self._subscriptions: dict[
            tuple[ReactiveEmitter, ReactiveSubscriber], AsyncDisposable
        ] = {}

    @classmethod
    async def create(cls) -> Self:
        self = cls()
        await self.add_async_subscriber(DatabaseSubscriber())
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

        logger.info(f"Added emitter to alert manager: {raw_emitter}")

    async def add_async_subscriber(self, raw_subscriber: AsyncSubscriber) -> None:
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

        logger.info(f"Added subscriber to alert manager: {raw_subscriber}")

    async def add_sync_subscriber(self, raw_subscriber: SyncSubscriber) -> None:
        assert all(
            raw_subscriber is not subscriber.raw_subscriber
            for subscriber in self._subscribers
        )

        raw_async_subscriber = AsyncSubscriberWrapper(raw_subscriber)
        await self.add_async_subscriber(raw_async_subscriber)

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

        logger.info(f"Removed emitter from alert manager: {raw_emitter}")
        return True

    async def remove_subscriber(
        self, raw_subscriber: AsyncSubscriber | SyncSubscriber
    ) -> bool:
        subscriber = next(
            (
                subscriber
                for subscriber in self._subscribers
                if subscriber.raw_subscriber is raw_subscriber
                or (
                    isinstance(subscriber.raw_subscriber, AsyncSubscriberWrapper)
                    and subscriber.raw_subscriber.wrapped is raw_subscriber
                )
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
        logger.info(f"Removed subscriber from alert manager: {raw_subscriber}")

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

        logger.info(f"Started emitter in alert manager: {emitter}")

    def _stop_emitter(self, emitter: ReactiveEmitter) -> bool:
        task = self._emitters[emitter]
        if task is not None:
            task.cancel()
            logger.info(f"Stopped emitter in alert manager: {emitter}")
            return True
        return False


class SubscriberStatus(Enum):
    Ok = 0
    Error = 1


@dataclass
class ManagedSubscriber:
    db_info: DbSubscriber

    status: SubscriberStatus

    plugin_desc: Optional[PluginDescriptor] = None
    component: Optional[ComponentDescriptor] = None
    raw: Optional[AsyncSubscriber | SyncSubscriber] = None

    @property
    def id(self) -> int:
        return self.db_info.id

    @property
    def name(self) -> str:
        return self.db_info.name

    @property
    def enabled(self) -> bool:
        return self.db_info.enabled

    @property
    def plugin_name(self) -> str:
        return self.db_info.plugin_name

    @property
    def component_name(self) -> str:
        return self.db_info.component_name

    @property
    def config(self) -> dict[str, Any]:
        # Guaranteed to be a dict since we only ever save a dict to the db.
        config = typing.cast(dict[str, Any], self.db_info.config)
        return config


class SubscriberManager:
    def __init__(
        self,
        subscription_registrar: SubscriptionRegistrar,
        plugin_manager: PluginManager,
    ) -> None:
        self._subscription_registrar: SubscriptionRegistrar = subscription_registrar
        self._plugin_manager: PluginManager = plugin_manager
        self._managed_subscribers: dict[int, ManagedSubscriber] = {}

    @property
    def managed_subscribers(self) -> dict[int, ManagedSubscriber]:
        return self._managed_subscribers

    def available_subscriber_components(self) -> list[ComponentDescriptor]:
        """
        Returns a list of available subscriber components based on the loaded plugins.
        """
        return [
            component
            for plugin_desc in self._plugin_manager.plugin_descriptors
            if plugin_desc.plugin is not None
            for component in plugin_desc.plugin.components
            if component.kind
            in {ComponentKind.AsyncSubscriber, ComponentKind.SyncSubscriber}
        ]

    async def load_from_db(self) -> None:
        async for db_info in DbSubscriber.all():
            managed_subscriber = ManagedSubscriber(
                db_info=db_info,
                status=SubscriberStatus.Ok,
            )
            self._managed_subscribers[managed_subscriber.id] = managed_subscriber

            plugin_desc = self._plugin_manager.find_plugin_desc(
                lambda plugin_desc: plugin_desc.name == db_info.plugin_name
            )

            if plugin_desc is None or plugin_desc.plugin is None:
                managed_subscriber.status = SubscriberStatus.Error
                logger.info(
                    f'Recreated subscriber from database for "{db_info.name}" (id: {db_info.id})'
                    f"but could not find or load subscriber plugin"
                )
                return

            component = plugin_desc.plugin.find_component(
                lambda comp: comp.display_name == db_info.component_name
            )
            if component is None:
                managed_subscriber.status = SubscriberStatus.Error
                logger.info(
                    f'Recreated subscriber from database for "{db_info.name}" (id: {db_info.id})'
                    f"but could not find subscriber component"
                )
                return

            managed_subscriber.plugin_desc = plugin_desc
            managed_subscriber.component = component
            logger.info(
                f'Recreated subscriber from database for "{db_info.name}" (id: {db_info.id})'
            )

            if managed_subscriber.enabled:
                await self._register_subscriber(managed_subscriber.id)

    async def add_subscriber(
        self,
        name: str,
        component: ComponentDescriptor,
        config: dict[str, Any],
    ) -> None:
        assert component.kind in {
            ComponentKind.AsyncSubscriber,
            ComponentKind.SyncSubscriber,
        }

        # Find the plugin for the component.
        _, plugin_desc = self._plugin_manager.find_component(
            lambda comp: comp is component
        )

        if plugin_desc is None:
            raise ValueError(
                "Failed to find corresponding plugin for subscriber component."
            )

        # Create an entry in the database.
        db_subscriber = DbSubscriber(
            name=name,
            enabled=False,
            plugin_name=plugin_desc.name,
            component_name=component.display_name,
            config=config,
        )
        await db_subscriber.save()
        logger.info(f'Saved "{db_subscriber.name}" subscriber to database')

        # Create the managed subscriber.
        managed_subscriber = ManagedSubscriber(
            db_info=db_subscriber,
            status=SubscriberStatus.Ok,
            plugin_desc=plugin_desc,
            component=component,
        )
        self._managed_subscribers[db_subscriber.id] = managed_subscriber
        logger.info(f'Created subscriber for "{managed_subscriber.name}"')

    async def enable_subscriber(self, id: int) -> None:
        managed_subscriber = self._managed_subscribers[id]

        # Update the corresponding entry in the database.
        managed_subscriber.db_info.enabled = True
        await managed_subscriber.db_info.save()

        managed_subscriber.status = SubscriberStatus.Ok
        # self._signal_status_change(managed_subscriber)

        await self._register_subscriber(id)

        logger.info(
            f'Enabled subscriber "{managed_subscriber.name}" (id: {managed_subscriber.id})'
        )

    async def disable_subscriber(self, id: int) -> None:
        managed_subscriber = self._managed_subscribers[id]

        # Update the corresponding entry in the database.
        managed_subscriber.db_info.enabled = False
        await managed_subscriber.db_info.save()

        await self._deregister_subscriber(id)

        logger.info(
            f'Disabled subscriber "{managed_subscriber.name}" (id: {managed_subscriber.id})'
        )

    async def _register_subscriber(self, id: int) -> bool:
        managed_subscriber = self._managed_subscribers[id]

        # Raw subscriber already created.
        if managed_subscriber.raw is not None:
            return False

        if managed_subscriber.component is None:
            # TODO: handle error
            logger.info(
                "Tried to create raw subscriber for "
                f'"{managed_subscriber.name}" (id: {managed_subscriber.id}) '
                "but could not find component"
            )
            return False

        kwargs = managed_subscriber.config
        if managed_subscriber.component.args_transform is not None:
            kwargs = managed_subscriber.component.args_transform(
                managed_subscriber.config
            )
        raw_subscriber = managed_subscriber.component.cls(**kwargs)

        if managed_subscriber.component.kind == ComponentKind.AsyncSubscriber:
            await self._subscription_registrar.add_async_subscriber(raw_subscriber)
        else:
            assert managed_subscriber.component.kind == ComponentKind.SyncSubscriber
            await self._subscription_registrar.add_sync_subscriber(raw_subscriber)

        managed_subscriber.raw = raw_subscriber
        return True

    async def _deregister_subscriber(self, id: int) -> bool:
        managed_subscriber = self._managed_subscribers[id]

        if managed_subscriber.raw is not None:
            await self._subscription_registrar.remove_subscriber(managed_subscriber.raw)
            managed_subscriber.raw = None
            return True
        return False
