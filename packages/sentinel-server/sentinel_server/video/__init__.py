import dataclasses
import logging
from enum import Enum
from typing import Any, Optional

import cv2
from aioreactive import AsyncObservable, AsyncObserver, AsyncSubject
from sentinel_core.plugins import ComponentDescriptor, ComponentKind
from sentinel_core.video import Frame, VideoStream, VideoStreamNoDataException

from sentinel_server.models import VideoSource as DbVideoSource
from sentinel_server.plugins import PluginDescriptor, PluginManager

logger = logging.getLogger(__name__)


class ReactiveVideoStream(AsyncObservable[Frame]):
    def __init__(self, raw_stream: VideoStream):
        self._raw_stream: VideoStream = raw_stream
        self._run: bool = False
        self._subject: AsyncSubject[Frame] = AsyncSubject()

    @property
    def stream(self):
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
            await self._subject.asend(frame)

    def pause(self):
        self._run = False

    async def stop(self):
        self._run = False
        await self._subject.aclose()


class OpenCVViewer(AsyncObserver[Frame]):
    def __init__(self, win_name: str, always_show: bool = False):
        self._win_name = win_name
        self._always_show = always_show

    async def asend(self, frame: Frame):
        cv2.imshow(self._win_name, frame.data)

    async def athrow(self, error):
        if not self._always_show:
            cv2.destroyWindow(self._win_name)

    async def aclose(self):
        if not self._always_show:
            cv2.destroyWindow(self._win_name)


class VideoSourceStatus(Enum):
    Ok = 0
    Error = 1


@dataclasses.dataclass
class VideoSource:
    id: int
    name: str
    enabled: bool
    status: VideoSourceStatus
    plugin_name: str
    component_name: str
    plugin_desc: Optional[PluginDescriptor] = None
    component: Optional[ComponentDescriptor] = None
    video_stream: Optional[ReactiveVideoStream] = None


class VideoSourceManager:
    def __init__(self, plugin_manager: PluginManager):
        self._plugin_manager: PluginManager = plugin_manager
        self._video_sources: dict[int, VideoSource] = {}

    async def load_video_sources_from_db(self) -> None:
        async for db_vid_src in DbVideoSource.all():
            vid_src = VideoSource(
                id=db_vid_src.id,
                name=db_vid_src.name,
                enabled=db_vid_src.enabled,
                status=VideoSourceStatus.Ok,
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
                    f'Created video stream for "{db_vid_src.name}" but could not find plugin'
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
                    f'Created video stream for "{db_vid_src.name}"'
                    "but could not find video stream component"
                )
                continue

            vid_src.component = comp

            # Initialise the raw video stream.
            config = db_vid_src.config
            raw_vidstream = comp.cls(**config)
            vid_src.video_stream = ReactiveVideoStream(raw_vidstream)
            logger.info(f'Created video stream for "{db_vid_src.name}" without error')

            # TODO: start capturing video data

    async def add_video_source(
        self, name: str, component: ComponentDescriptor, kwargs: dict[str, Any]
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
            config=kwargs,
        )
        await db_vid_src.save()
        logger.info(f'Saved "{db_vid_src.name}" video source to database')

        # Create the video source.
        raw_vidstream = component.cls(**kwargs)
        vid_stream = ReactiveVideoStream(raw_vidstream)
        vid_src = VideoSource(
            id=db_vid_src.id,
            name=name,
            enabled=False,
            status=VideoSourceStatus.Ok,
            plugin_name=db_vid_src.plugin_name,
            component_name=db_vid_src.component_name,
            plugin_desc=plugin_desc,
            component=component,
            video_stream=vid_stream,
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
            if component.kind == ComponentKind.VideoStream
        ]

    def video_sources(self) -> dict[int, VideoSource]:
        return self._video_sources
