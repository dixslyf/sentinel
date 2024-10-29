import asyncio
import dataclasses
import logging
import typing
from enum import Enum
from typing import Any, Optional, Self

from aioreactive import AsyncDisposable, AsyncObservable, AsyncObserver, AsyncSubject
from sentinel_core.plugins import ComponentDescriptor, ComponentKind
from sentinel_core.video import (
    AsyncVideoStream,
    Frame,
    SyncVideoStream,
    VideoStreamNoDataException,
)

import sentinel_server.tasks
from sentinel_server.models import VideoSource as DbVideoSource
from sentinel_server.plugins import PluginDescriptor, PluginManager
from sentinel_server.video.detect import ReactiveDetector

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
    db_info: DbVideoSource

    status: VideoSourceStatus
    subscribers: dict[AsyncObserver, Optional[AsyncDisposable]] = dataclasses.field(
        default_factory=lambda: {}
    )

    vidstream_plugin_desc: Optional[PluginDescriptor] = None
    vidstream_component: Optional[ComponentDescriptor] = None
    video_stream: Optional[ReactiveVideoStream] = None

    detector_plugin_desc: Optional[PluginDescriptor] = None
    detector_component: Optional[ComponentDescriptor] = None
    detector: Optional[ReactiveDetector] = None
    detector_sub: Optional[AsyncDisposable] = None

    task: Optional[asyncio.Task] = None

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
    def vidstream_plugin_name(self) -> str:
        return self.db_info.vidstream_plugin_name

    @property
    def vidstream_component_name(self) -> str:
        return self.db_info.vidstream_component_name

    @property
    def vidstream_config(self) -> dict[str, Any]:
        # Guaranteed to be a dict since we only ever save a dict to the db.
        vidstream_config = typing.cast(dict[str, Any], self.db_info.vidstream_config)
        return vidstream_config

    @property
    def detector_plugin_name(self) -> str:
        return self.db_info.detector_plugin_name

    @property
    def detector_component_name(self) -> str:
        return self.db_info.detector_component_name

    @property
    def detector_config(self) -> dict[str, Any]:
        # Guaranteed to be a dict since we only ever save a dict to the db.
        detector_config = typing.cast(dict[str, Any], self.db_info.detector_config)
        return detector_config


class VideoSourceManager:
    def __init__(self, plugin_manager: PluginManager) -> None:
        self._plugin_manager: PluginManager = plugin_manager
        self._video_sources: dict[int, VideoSource] = {}

    async def load_video_sources_from_db(self) -> None:
        async for db_vid_src in DbVideoSource.all():
            vid_src = VideoSource(
                db_info=db_vid_src,
                status=VideoSourceStatus.Ok,
            )
            self._video_sources[vid_src.id] = vid_src

            # Find the video stream plugin.
            vid_src.vidstream_plugin_desc = (
                self._plugin_manager.find_plugin_desc_by_name(
                    db_vid_src.vidstream_plugin_name
                )
            )

            # If we can't find the plugin, then we just set the status to error.
            if vid_src.vidstream_plugin_desc is None:
                vid_src.status = VideoSourceStatus.Error
                logger.info(
                    f'Recreated video source from database for "{db_vid_src.name}" (id: {db_vid_src.id})'
                    "but could not find video stream plugin"
                )
                continue

            # If the plugin isn't loaded (i.e., it is not part of the whitelist),
            # then we set error as well.
            if vid_src.vidstream_plugin_desc.plugin is None:
                vid_src.status = VideoSourceStatus.Error
                logger.info(
                    f'Recreated video source from database for "{db_vid_src.name}" (id: {db_vid_src.id})'
                    "but video stream plugin is not loaded"
                )
                continue

            # Find the video stream component.
            vid_src.vidstream_component = (
                vid_src.vidstream_plugin_desc.plugin.find_component_by_name(
                    db_vid_src.vidstream_component_name
                )
            )

            # Likewise, if we can't find the video stream component,
            # then we just set the status to error.
            if vid_src.vidstream_component is None:
                vid_src.status = VideoSourceStatus.Error
                logger.info(
                    f'Recreated video source from database for "{db_vid_src.name}" (id: {db_vid_src.id})'
                    "but could not find video stream component"
                )
                continue

            # Find the detector plugin.
            vid_src.detector_plugin_desc = (
                self._plugin_manager.find_plugin_desc_by_name(
                    db_vid_src.detector_plugin_name
                )
            )

            # If we can't find the plugin, then we just set the status to error.
            if vid_src.detector_plugin_desc is None:
                vid_src.status = VideoSourceStatus.Error
                logger.info(
                    f'Recreated video source from database for "{db_vid_src.name}" (id: {db_vid_src.id})'
                    "but could not find detector plugin"
                )
                continue

            # If the plugin isn't loaded (i.e., it is not part of the whitelist),
            # then we set error as well.
            if vid_src.detector_plugin_desc.plugin is None:
                vid_src.status = VideoSourceStatus.Error
                logger.info(
                    f'Recreated video source from database for "{db_vid_src.name}" (id: {db_vid_src.id})'
                    "but detector plugin is not loaded"
                )
                continue

            # Find the video stream component.
            vid_src.detector_component = (
                vid_src.detector_plugin_desc.plugin.find_component_by_name(
                    db_vid_src.detector_component_name
                )
            )

            # Likewise, if we can't find the detector component,
            # then we just set the status to error.
            if vid_src.detector_component is None:
                vid_src.status = VideoSourceStatus.Error
                logger.info(
                    f'Recreated video source from database for "{db_vid_src.name}" (id: {db_vid_src.id})'
                    "but could not find detector component"
                )
                continue

            logger.info(
                f'Recreated video source from database for "{db_vid_src.name}" (id: {db_vid_src.id})'
            )

            if vid_src.enabled:
                self._start_video_stream(vid_src.id)
                await self._start_detector(vid_src.id)

    async def add_video_source(
        self,
        name: str,
        vidstream_comp: ComponentDescriptor,
        vidstream_config: dict[str, Any],
        detector_comp: ComponentDescriptor,
        detector_config: dict[str, Any],
    ) -> None:
        assert (
            vidstream_comp.kind == ComponentKind.AsyncVideoStream
            or vidstream_comp.kind == ComponentKind.SyncVideoStream
        )

        assert (
            detector_comp.kind == ComponentKind.AsyncDetector
            or detector_comp.kind == ComponentKind.SyncDetector
        )

        # Find the plugin for the video stream component.
        vidstream_plugin_desc = next(
            (
                plugin_desc
                for plugin_desc in self._plugin_manager.plugin_descriptors
                if plugin_desc.plugin is not None
                for plugin_comp in plugin_desc.plugin.components
                if plugin_comp is vidstream_comp
            ),
            None,
        )
        if vidstream_plugin_desc is None:
            raise ValueError(
                "Failed to find corresponding plugin for video stream component."
            )

        # Find the plugin for the detector component.
        detector_plugin_desc = next(
            (
                plugin_desc
                for plugin_desc in self._plugin_manager.plugin_descriptors
                if plugin_desc.plugin is not None
                for plugin_comp in plugin_desc.plugin.components
                if plugin_comp is detector_comp
            ),
            None,
        )
        if detector_plugin_desc is None:
            raise ValueError(
                "Failed to find corresponding plugin for detector component."
            )

        # Create an entry in the database.
        db_vid_src = DbVideoSource(
            name=name,
            enabled=False,
            vidstream_plugin_name=vidstream_plugin_desc.name,
            vidstream_component_name=vidstream_comp.display_name,
            vidstream_config=vidstream_config,
            detector_plugin_name=detector_plugin_desc.name,
            detector_component_name=detector_comp.display_name,
            detector_config=detector_config,
        )
        await db_vid_src.save()
        logger.info(f'Saved "{db_vid_src.name}" video source to database')

        # Create the video source.
        vid_src = VideoSource(
            db_info=db_vid_src,
            status=VideoSourceStatus.Ok,
            vidstream_plugin_desc=vidstream_plugin_desc,
            vidstream_component=vidstream_comp,
            detector_plugin_desc=detector_plugin_desc,
            detector_component=detector_comp,
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
            if plugin_desc.plugin is not None
            for component in plugin_desc.plugin.components
            if component.kind == ComponentKind.AsyncVideoStream
            or component.kind == ComponentKind.SyncVideoStream
        ]

    def available_detector_components(self) -> list[ComponentDescriptor]:
        """
        Returns a list of available detector components based on the loaded plugins.
        """
        return [
            component
            for plugin_desc in self._plugin_manager.plugin_descriptors
            if plugin_desc.plugin is not None
            for component in plugin_desc.plugin.components
            if component.kind == ComponentKind.AsyncDetector
            or component.kind == ComponentKind.SyncDetector
        ]

    @property
    def video_sources(self) -> dict[int, VideoSource]:
        return self._video_sources

    async def enable_video_source(self, id: int) -> None:
        vid_src = self._video_sources[id]

        # Update the corresponding entry in the database.
        vid_src.db_info.enabled = True
        await vid_src.db_info.save()

        logger.info(f'Enabled video source "{vid_src.name}" (id: {vid_src.id})')

        # TODO: error handling
        self._start_video_stream(id)

        # TODO: error handling
        await self._start_detector(id)

        # Subscribe existing observers.
        for observer in vid_src.subscribers.keys():
            await self.subscribe_to(id, observer)

    async def disable_video_source(self, id: int) -> None:
        vid_src = self._video_sources[id]

        # Update the corresponding entry in the database.
        vid_src.db_info.enabled = False
        await vid_src.db_info.save()

        logger.info(f'Disabled video source "{vid_src.name}" (id: {vid_src.id})')

        # Unsubscribe observers, but continue keeping track of them for when the
        # video stream is restarted.
        for observer in vid_src.subscribers.keys():
            await self.unsubscribe_from(id, observer, _hard=False)

        await self._stop_detector(id)
        self._stop_video_stream(id)

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

    def _start_video_stream(self, id: int) -> bool:
        vid_src = self._video_sources[id]

        # Video stream is already running.
        if vid_src.video_stream is not None:
            return True

        # If we cannot find the video stream component, then we can't create the video stream
        # since we don't have access to the video stream class.
        if vid_src.vidstream_component is None:
            return False

        # Determine the keyword arguments for creating the video stream.
        kwargs = vid_src.vidstream_config
        if vid_src.vidstream_component.args_transform is not None:
            kwargs = vid_src.vidstream_component.args_transform(
                vid_src.vidstream_config
            )

        # Initialise the raw video stream.
        raw_vidstream = vid_src.vidstream_component.cls(**kwargs)

        # Create the reactive video stream.
        if vid_src.vidstream_component.kind == ComponentKind.AsyncVideoStream:
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
                    f'Stopped video stream for "{vid_src.name}" (id: {vid_src.name})'
                )
                raise

        task = asyncio.create_task(video_source_task())
        vid_src.task = task
        logger.info(f'Started video stream for "{vid_src.name}" (id: {vid_src.id})')

        return True

    async def _start_detector(self, id: int) -> bool:
        vid_src = self._video_sources[id]

        # Should only be called after the reactive video stream has been initialised.
        assert vid_src.video_stream is not None

        # Detector is already running.
        if vid_src.detector is not None:
            return True

        # If we cannot find the detector component, then we can't create the detector
        # since we don't have access to the detector class.
        if vid_src.detector_component is None:
            return False

        # Determine the keyword arguments for creating the detector.
        kwargs = vid_src.detector_config
        if vid_src.detector_component.args_transform is not None:
            kwargs = vid_src.detector_component.args_transform(vid_src.detector_config)

        # Initialise the raw detector.
        raw_detector = vid_src.detector_component.cls(**kwargs)

        # Create the reactive detector.
        if vid_src.detector_component.kind == ComponentKind.AsyncDetector:
            vid_src.detector = ReactiveDetector(raw_detector)
        else:  # Synchronous detector
            vid_src.detector = ReactiveDetector.from_sync_detector(raw_detector)

        vid_src.detector_sub = await vid_src.video_stream.subscribe_async(
            vid_src.detector
        )

        logger.info(f'Started detector for "{vid_src.name}" (id: {vid_src.id})')

        return True

    def _stop_video_stream(self, id: int) -> bool:
        vid_src = self._video_sources[id]

        # Video stream wasn't running in the first place.
        if vid_src.task is None:
            return False

        vid_src.task.cancel()
        logging.info(
            f'Cancellation request sent to video source task for "{vid_src.name}" (id: {vid_src.id})'
        )

        return True

    async def _stop_detector(self, id: int) -> bool:
        vid_src = self._video_sources[id]

        # Detector wasn't running in the first place.
        if vid_src.detector is None:
            return False

        assert vid_src.detector_sub is not None

        await vid_src.detector_sub.dispose_async()
        vid_src.detector = None
        vid_src.detector_sub = None

        logging.info(f'Stopped detector for "{vid_src.name}" (id: {vid_src.id})')

        return True
