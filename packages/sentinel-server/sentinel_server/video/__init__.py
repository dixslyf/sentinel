import asyncio
import dataclasses
import logging
import typing
from enum import Enum
from typing import Any, Optional, Self

import sentinel_server.tasks
from aioreactive import AsyncDisposable, AsyncObservable, AsyncObserver, AsyncSubject
from sentinel_core.plugins import ComponentDescriptor, ComponentKind
from sentinel_core.video import (
    AsyncVideoStream,
    Frame,
    SyncVideoStream,
    VideoStreamNoDataException,
)
from sentinel_server.models import VideoSource as DbVideoSource
from sentinel_server.plugins import PluginDescriptor, PluginManager

logger = logging.getLogger(__name__)


class AsyncVideoStreamWrapper(AsyncVideoStream):
    """
    A wrapper around a synchronous video stream to make it asynchronous.
    """

    def __init__(self, sync_stream: SyncVideoStream):
        self._sync_stream: SyncVideoStream = sync_stream

    async def next_frame(self) -> Optional[Frame]:
        return await sentinel_server.tasks.run_in_thread(self._sync_stream.next_frame)

    async def clean_up(self) -> None:
        await sentinel_server.tasks.run_in_thread(self._sync_stream.clean_up)


class ReactiveVideoStream(AsyncObservable[Frame]):
    def __init__(self, raw_stream: AsyncVideoStream) -> None:
        self._raw_stream: AsyncVideoStream = raw_stream
        self._run: bool = False
        self._subject: AsyncSubject[Frame] = AsyncSubject()

    @classmethod
    def from_sync_stream(cls, raw_stream: SyncVideoStream) -> Self:
        async_stream = AsyncVideoStreamWrapper(raw_stream)
        return cls(async_stream)

    @property
    def stream(self) -> AsyncVideoStream:
        return self._raw_stream

    async def subscribe_async(self, observer):
        return await self._subject.subscribe_async(observer)

    async def start(self):
        self._run = True
        while self._run:
            frame = await self._raw_stream.next_frame()
            if frame is None:
                exc = VideoStreamNoDataException(
                    "No data in the underlying video stream"
                )
                await self._subject.athrow(exc)
            else:
                await self._subject.asend(frame)

    async def stop(self):
        self._run = False
        await self._raw_stream.clean_up()
        await self._subject.aclose()


class VideoSourceStatus(Enum):
    Ok = 0
    Error = 1


@dataclasses.dataclass
class VideoSource:
    id: int
    name: str
    enabled: bool
    status: VideoSourceStatus
    config: dict[str, Any]

    plugin_name: str
    component_name: str

    subscribers: dict[AsyncObserver, Optional[AsyncDisposable]] = dataclasses.field(
        default_factory=lambda: {}
    )

    plugin_desc: Optional[PluginDescriptor] = None
    component: Optional[ComponentDescriptor] = None

    video_stream: Optional[ReactiveVideoStream] = None
    task: Optional[asyncio.Task] = None


class VideoSourceManager:
    def __init__(self, plugin_manager: PluginManager) -> None:
        self._plugin_manager: PluginManager = plugin_manager
        self._video_sources: dict[int, VideoSource] = {}

    async def load_video_sources_from_db(self) -> None:
        async for db_vid_src in DbVideoSource.all():
            vid_src = VideoSource(
                id=db_vid_src.id,
                name=db_vid_src.name,
                enabled=db_vid_src.enabled,
                status=VideoSourceStatus.Ok,
                config=db_vid_src.config,
                plugin_name=db_vid_src.plugin_name,
                component_name=db_vid_src.component_name,
            )
            self._video_sources[vid_src.id] = vid_src

            # Find the plugin.
            plugin_desc = next(
                (
                    plugin_desc
                    for plugin_desc in self._plugin_manager.plugin_descriptors
                    if plugin_desc.name == db_vid_src.plugin_name
                ),
                None,
            )

            # If we can't find the plugin, then we just set the status to error.
            if plugin_desc is None:
                vid_src.status = VideoSourceStatus.Error
                logger.info(
                    f'Recreated video source from database for "{db_vid_src.name}" (id: {db_vid_src.id})'
                    "but could not find video stream component"
                )
                continue
            vid_src.plugin_desc = plugin_desc

            # Find the video stream component.
            comp = next(
                (
                    comp
                    for comp in plugin_desc.plugin.components
                    if comp.display_name == db_vid_src.component_name
                ),
                None,
            )

            # Likewise, if we can't find the video stream component,
            # then we just set the status to error.
            if comp is None:
                vid_src.status = VideoSourceStatus.Error
                logger.info(
                    f'Recreated video source from database for "{db_vid_src.name}" (id: {db_vid_src.id})'
                    "but could not find video stream component"
                )
                continue
            vid_src.component = comp

            logger.info(
                f'Recreated video source from database for "{db_vid_src.name}" (id: {db_vid_src.id})'
            )

            if vid_src.enabled:
                self._start_video_source(vid_src.id)

    async def add_video_source(
        self, name: str, component: ComponentDescriptor, config: dict[str, Any]
    ) -> None:
        # Find the corresponding plugin.
        plugin_desc = next(
            (
                plugin_desc
                for plugin_desc in self._plugin_manager.plugin_descriptors
                for plugin_comp in plugin_desc.plugin.components
                if plugin_comp is component
            ),
            None,
        )
        if plugin_desc is None:
            raise ValueError("Failed to find corresponding plugin for component.")

        # Create an entry in the database.
        db_vid_src = DbVideoSource(
            name=name,
            plugin_name=plugin_desc.name,
            enabled=False,
            component_name=component.display_name,
            config=config,
        )
        await db_vid_src.save()
        logger.info(f'Saved "{db_vid_src.name}" video source to database')

        # Create the video source.
        vid_src = VideoSource(
            id=db_vid_src.id,
            name=name,
            enabled=False,
            status=VideoSourceStatus.Ok,
            config=config,
            plugin_name=db_vid_src.plugin_name,
            component_name=db_vid_src.component_name,
            plugin_desc=plugin_desc,
            component=component,
        )
        self._video_sources[db_vid_src.id] = vid_src
        logger.info(f'Created video source for "{vid_src.name}"')

    def available_vidstream_components(self) -> list[ComponentDescriptor]:
        """
        Returns a list of available video stream components based on the loaded plugins.
        """
        return [
            component
            for plugin_desc in self._plugin_manager.plugin_descriptors
            for component in plugin_desc.plugin.components
            if component.kind == ComponentKind.AsyncVideoStream
            or component.kind == ComponentKind.SyncVideoStream
        ]

    @property
    def video_sources(self) -> dict[int, VideoSource]:
        return self._video_sources

    async def enable_video_source(self, id: int) -> None:
        vid_src = self._video_sources[id]
        vid_src.enabled = True

        # Update the corresponding entry in the database.
        db_vid_src = await DbVideoSource.get(id=vid_src.id)
        db_vid_src.enabled = True
        await db_vid_src.save()

        logger.info(f'Enabled video source "{vid_src.name}" (id: {vid_src.id})')

        self._start_video_source(id)

        # Subscribe observers.
        for observer in vid_src.subscribers.keys():
            await self.subscribe_to(id, observer)

    async def disable_video_source(self, id: int) -> None:
        vid_src = self._video_sources[id]
        vid_src.enabled = False

        # Update the corresponding entry in the database.
        db_vid_src = await DbVideoSource.get(id=vid_src.id)
        db_vid_src.enabled = False
        await db_vid_src.save()

        logger.info(f'Disabled video source "{vid_src.name}" (id: {vid_src.id})')

        # Unsubscribe observers, but continue keeping track of them for when the
        # video stream is restarted.
        for observer in vid_src.subscribers.keys():
            await self.unsubscribe_from(id, observer, _hard=False)

        self._stop_video_source(id)

    async def subscribe_to(self, id: int, observer: AsyncObserver[Frame]) -> None:
        vid_src = self._video_sources[id]
        vid_src.subscribers[observer] = None

        # If the video stream is currently running,
        # immediately subscribe the observer to the frames.
        if vid_src.video_stream is not None:
            subscription = await vid_src.video_stream.subscribe_async(observer)
            vid_src.subscribers[observer] = subscription

        logger.info(f'Subscription added to "{vid_src.name}" (id: {id})')

    async def unsubscribe_from(
        self, id: int, observer: AsyncObserver[Frame], _hard: bool = True
    ) -> None:
        vid_src = self._video_sources[id]
        subscription = vid_src.subscribers[observer]
        if subscription is not None:
            await subscription.dispose_async()

        if _hard:
            del vid_src.subscribers[observer]

        logger.info(
            f'Subscription removed from "{vid_src.name}" (id: {id}) {"(hard)" if _hard else ""}'
        )

    def _start_video_source(self, id: int) -> bool:
        vid_src = self._video_sources[id]

        # Video stream is already running.
        if vid_src.video_stream is not None:
            return True

        # If we cannot find the video stream component, then we can't create the video stream
        # since we don't have access to the video stream class.
        if vid_src.component is None:
            return False

        # Determine the keyword arguments for creating the video stream.
        kwargs = vid_src.config
        if vid_src.component.args_transform is not None:
            kwargs = vid_src.component.args_transform(vid_src.config)

        # Initialise the raw video stream.
        raw_vidstream = vid_src.component.cls(**kwargs)

        # Create the reactive video stream.
        if vid_src.component.kind == ComponentKind.AsyncVideoStream:
            vid_src.video_stream = ReactiveVideoStream(raw_vidstream)
        else:  # Synchronous video stream
            vid_src.video_stream = ReactiveVideoStream.from_sync_stream(raw_vidstream)

        # Function to be scheduled as an asyncio task.
        async def video_source_task() -> None:
            # Since we check whether the video stream is None earlier,
            # we can be sure that the video stream is not None.
            video_stream = typing.cast(ReactiveVideoStream, vid_src.video_stream)
            try:
                await video_stream.start()
            except asyncio.CancelledError:  # For stopping the video stream.
                await video_stream.stop()
                vid_src.video_stream = None
                vid_src.task = None
                logger.info(
                    f'Stopped video source "{vid_src.name}" (id: {vid_src.name})'
                )
                raise

        task = asyncio.create_task(video_source_task())
        vid_src.task = task
        logger.info(f'Started video source "{vid_src.name}" (id: {vid_src.id})')

        return True

    def _stop_video_source(self, id: int) -> bool:
        vid_src = self._video_sources[id]

        # Video stream wasn't running in the first place.
        if vid_src.task is None:
            return False

        vid_src.task.cancel()
        logging.info(
            f'Cancellation request sent to video source task for "{vid_src.name}" (id: {vid_src.id})'
        )

        return True
