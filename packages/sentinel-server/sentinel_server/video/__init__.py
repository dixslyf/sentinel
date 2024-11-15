import asyncio
import dataclasses
import logging
import math
import typing
from asyncio import Queue
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional, Self

from aioreactive import AsyncDisposable, AsyncObservable, AsyncObserver, AsyncSubject
from sentinel_core.alert import Alert, Emitter
from sentinel_core.plugins import ComponentDescriptor, ComponentKind
from sentinel_core.video import (
    AsyncVideoStream,
    Frame,
    SyncVideoStream,
    VideoStreamNoDataException,
)
from sentinel_core.video.detect import DetectionResult

import sentinel_server.tasks
from sentinel_server.alert import AlertManager, SubscriptionRegistrar
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

    subscribers: dict[AsyncObserver[DetectionResult], Optional[AsyncDisposable]] = (
        dataclasses.field(default_factory=lambda: {})
    )

    vidstream_plugin_desc: Optional[PluginDescriptor] = None
    vidstream_component: Optional[ComponentDescriptor] = None
    video_stream: Optional[ReactiveVideoStream] = None

    detector_plugin_desc: Optional[PluginDescriptor] = None
    detector_component: Optional[ComponentDescriptor] = None
    detector: Optional[ReactiveDetector] = None
    detector_sub: Optional[AsyncDisposable] = None
    emitter: Optional[Emitter] = None

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
    def detect_interval(self) -> float:
        return self.db_info.detect_interval

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


class VideoSourceAlertEmitter(Emitter, AsyncObserver[DetectionResult]):
    def __init__(self, vid_src: VideoSource):
        if vid_src.detector is None:
            raise ValueError("Video source does not have a detector")

        self._vid_src = vid_src
        self._queue: Queue = Queue()

        # Delayed initialisation in `create()`.
        self._sub: Optional[AsyncDisposable] = None

    @classmethod
    async def create(cls, vid_src: VideoSource) -> Self:
        self = cls(vid_src)

        assert self._vid_src.detector is not None
        self._sub = await self._vid_src.detector.subscribe_async(self)

        return self

    async def next_alert(self) -> Alert:
        alert = await self._queue.get()
        self._queue.task_done()
        return alert

    async def asend(self, dr: DetectionResult) -> None:
        if not dr.detections:
            return

        objects: list[str] = []
        for detection in dr.detections:
            # Choose the most likely object category.
            object_cat = max(
                detection.pred_categories,
                key=lambda cat: cat.score if cat.score is not None else -math.inf,
            )
            objects.append(object_cat.name)

        desc: str = f"Detected: {", ".join(objects)}"
        alert = Alert(
            header="Camera Alert",
            description=desc,
            source=self._vid_src.name,
            source_type="Video Source",
            timestamp=datetime.now(),
            data={"detections": objects},
        )
        await self._queue.put(alert)

    async def athrow(self, error: Exception):
        raise error

    async def aclose(self):
        pass


class VideoSourceManager:
    def __init__(
        self,
        plugin_manager: PluginManager,
        alert_manager: AlertManager,
        subscription_registrar: SubscriptionRegistrar,
    ) -> None:
        self._plugin_manager: PluginManager = plugin_manager
        self._alert_manager: AlertManager = alert_manager
        self._subscription_registrar: SubscriptionRegistrar = subscription_registrar
        self._video_sources: dict[int, VideoSource] = {}

        self._task_exception_callbacks: list[Callable[[BaseException], None]] = []
        self._status_change_callbacks: list[Callable[[VideoSource], None]] = []

    async def load_video_sources_from_db(self) -> None:
        async for db_vid_src in DbVideoSource.all():
            vid_src = VideoSource(
                db_info=db_vid_src,
                status=VideoSourceStatus.Ok,
            )
            self._video_sources[vid_src.id] = vid_src

            if not self._initialise_plugin_component(vid_src, "vidstream"):
                continue

            if not self._initialise_plugin_component(vid_src, "detector"):
                continue

            logger.info(
                f'Recreated video source from database for "{db_vid_src.name}" (id: {db_vid_src.id})'
            )

            if vid_src.enabled:
                self._start_video_stream(vid_src.id)
                await self._start_detector(vid_src.id)
                await self._register_emitter(vid_src.id)

    async def add_video_source(
        self,
        name: str,
        detect_interval: float,
        vidstream_comp: ComponentDescriptor,
        vidstream_config: dict[str, Any],
        detector_comp: ComponentDescriptor,
        detector_config: dict[str, Any],
    ) -> None:
        assert vidstream_comp.kind in {
            ComponentKind.AsyncVideoStream,
            ComponentKind.SyncVideoStream,
        }

        assert detector_comp.kind in {
            ComponentKind.AsyncDetector,
            ComponentKind.SyncDetector,
        }

        # Find the plugin for the video stream component.
        _, vidstream_plugin_desc = self._plugin_manager.find_component(
            lambda comp: comp is vidstream_comp
        )

        if vidstream_plugin_desc is None:
            raise ValueError(
                "Failed to find corresponding plugin for video stream component."
            )

        # Find the plugin for the detector component.
        _, detector_plugin_desc = self._plugin_manager.find_component(
            lambda comp: comp is detector_comp
        )

        if detector_plugin_desc is None:
            raise ValueError(
                "Failed to find corresponding plugin for detector component."
            )

        # Create an entry in the database.
        db_vid_src = DbVideoSource(
            name=name,
            enabled=False,
            detect_interval=detect_interval,
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

    async def remove_video_source(self, id: int) -> bool:
        vid_src = self._video_sources.get(id)
        if vid_src is None:
            return False

        await self.disable_video_source(id)
        await vid_src.db_info.delete()

        for subscription in vid_src.subscribers.values():
            if subscription is not None:
                await subscription.dispose_async()
        del self._video_sources[id]

        await self._alert_manager.mark_source_deleted(vid_src.name)

        logger.info(f'Deleted video source "{vid_src.name}" (id: {id})')

        return True

    def available_vidstream_components(self) -> list[ComponentDescriptor]:
        """
        Returns a list of available video stream components based on the loaded plugins.
        """
        return [
            component
            for plugin_desc in self._plugin_manager.plugin_descriptors
            if plugin_desc.plugin is not None
            for component in plugin_desc.plugin.components
            if component.kind
            in {ComponentKind.AsyncVideoStream, ComponentKind.SyncVideoStream}
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
            if component.kind
            in {ComponentKind.AsyncDetector, ComponentKind.SyncDetector}
        ]

    @property
    def video_sources(self) -> dict[int, VideoSource]:
        return self._video_sources

    async def enable_video_source(self, id: int) -> None:
        vid_src = self._video_sources[id]

        # Update the corresponding entry in the database.
        vid_src.db_info.enabled = True
        await vid_src.db_info.save()

        vid_src.status = VideoSourceStatus.Ok
        self._signal_status_change(vid_src)

        logger.info(f'Enabled video source "{vid_src.name}" (id: {vid_src.id})')

        # TODO: error handling
        self._start_video_stream(id)

        # TODO: error handling
        await self._start_detector(id)

        # Subscribe existing observers.
        for observer in vid_src.subscribers.keys():
            await self.subscribe_to(id, observer)

        await self._register_emitter(id)

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
        await self._stop_video_stream(id)

        await self._deregister_emitter(id)

    async def subscribe_to(
        self, id: int, observer: AsyncObserver[DetectionResult]
    ) -> None:
        vid_src = self._video_sources[id]
        vid_src.subscribers[observer] = None

        # If the detector is currently running,
        # immediately subscribe the observer to the detection results.
        if vid_src.detector is not None:
            subscription = await vid_src.detector.subscribe_async(observer)
            vid_src.subscribers[observer] = subscription

        logger.info(f'Subscription added to "{vid_src.name}" (id: {id})')

    async def unsubscribe_from(
        self, id: int, observer: AsyncObserver[DetectionResult], _hard: bool = True
    ) -> bool:
        vid_src = self._video_sources.get(id)
        if vid_src is None:
            return False

        subscription = vid_src.subscribers[observer]
        if subscription is not None:
            await subscription.dispose_async()
            vid_src.subscribers[observer] = None

        if _hard:
            del vid_src.subscribers[observer]

        logger.info(
            f'Subscription removed from "{vid_src.name}" (id: {id}) {"(hard)" if _hard else ""}'
        )
        return True

    def add_task_exception_callback(self, callback: Callable[[BaseException], None]):
        self._task_exception_callbacks.append(callback)

    def remove_task_exception_callback(self, callback: Callable[[BaseException], None]):
        self._task_exception_callbacks.remove(callback)

    def add_status_change_callback(self, callback: Callable[[VideoSource], None]):
        self._status_change_callbacks.append(callback)

    def remove_status_change_callback(self, callback: Callable[[VideoSource], None]):
        self._status_change_callbacks.remove(callback)

    def _signal_status_change(self, video_source: VideoSource) -> None:
        for callback in self._status_change_callbacks:
            callback(video_source)

    def _initialise_plugin_component(
        self, vid_src: VideoSource, component_type: str
    ) -> bool:
        assert component_type == "vidstream" or component_type == "detector"
        component_type_display = (
            "video stream" if component_type == "vidstream" else "detector"
        )

        db_info: DbVideoSource = vid_src.db_info

        plugin_name = getattr(db_info, f"{component_type}_plugin_name")
        component_name = getattr(db_info, f"{component_type}_component_name")

        plugin_desc = self._plugin_manager.find_plugin_desc(
            lambda plugin_desc: plugin_desc.name == plugin_name
        )
        if plugin_desc is None or plugin_desc.plugin is None:
            vid_src.status = VideoSourceStatus.Error
            logger.info(
                f'Recreated video source from database for "{db_info.name}" (id: {db_info.id})'
                f"but could not find or load {component_type_display} plugin"
            )
            return False

        component = plugin_desc.plugin.find_component(
            lambda comp: comp.display_name == component_name
        )
        if component is None:
            vid_src.status = VideoSourceStatus.Error
            logger.info(
                f'Recreated video source from database for "{db_info.name}" (id: {db_info.id})'
                f"but could not find {component_type_display} component"
            )
            return False

        setattr(vid_src, f"{component_type}_plugin_desc", plugin_desc)
        setattr(vid_src, f"{component_type}_component", component)
        return True

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
            await video_stream.start()

        vid_src.task = asyncio.create_task(video_source_task())
        vid_src.task.add_done_callback(self._task_done_callback)
        logger.info(f'Started video stream for "{vid_src.name}" (id: {vid_src.id})')

        return True

    def _task_done_callback(self, task: asyncio.Task):
        # Find the corresponding video source and set the task to None.
        for vid_src in self._video_sources.values():
            if vid_src.task is task:
                vid_src.task = None
                break

        # If there was an exception set the status of the video source to error
        # and call exception callbacks.
        if not task.cancelled():
            ex = task.exception()
            if ex is not None:
                vid_src.status = VideoSourceStatus.Error
                self._signal_status_change(vid_src)
                for callback in self._task_exception_callbacks:
                    callback(ex)

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
            vid_src.detector = ReactiveDetector(
                raw_detector, interval=vid_src.detect_interval
            )
        else:  # Synchronous detector
            vid_src.detector = ReactiveDetector.from_sync_detector(
                raw_detector, interval=vid_src.detect_interval
            )

        vid_src.detector_sub = await vid_src.video_stream.subscribe_async(
            vid_src.detector
        )

        logger.info(f'Started detector for "{vid_src.name}" (id: {vid_src.id})')

        return True

    async def _stop_video_stream(self, id: int) -> bool:
        vid_src = self._video_sources[id]

        # Video stream wasn't running in the first place.
        if vid_src.video_stream is None:
            return False

        await vid_src.video_stream.stop()
        vid_src.video_stream = None
        logger.info(f'Stopped video stream for "{vid_src.name}" (id: {vid_src.name})')

        return True

    async def _stop_detector(self, id: int) -> bool:
        vid_src = self._video_sources[id]

        # Detector wasn't running in the first place.
        if vid_src.detector is None:
            return False

        assert vid_src.detector_sub is not None

        await vid_src.detector_sub.dispose_async()
        await vid_src.detector.aclose()
        vid_src.detector = None
        vid_src.detector_sub = None

        logging.info(f'Stopped detector for "{vid_src.name}" (id: {vid_src.id})')

        return True

    async def _register_emitter(self, id: int) -> None:
        vid_src = self._video_sources[id]
        emitter = await VideoSourceAlertEmitter.create(vid_src)
        vid_src.emitter = emitter
        await self._subscription_registrar.add_emitter(emitter)

    async def _deregister_emitter(self, id: int) -> None:
        vid_src = self._video_sources[id]
        if vid_src.emitter is not None:
            await self._subscription_registrar.remove_emitter(vid_src.emitter)
            vid_src.emitter = None
