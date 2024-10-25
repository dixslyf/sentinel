import asyncio
from collections.abc import Iterable
from typing import Optional, Self

import cv2
import numpy as np
from sentinel_core.alert import Subscriber
from sentinel_core.plugins import (
    ComponentArgDescriptor,
    ComponentDescriptor,
    ComponentKind,
    Plugin,
)
from sentinel_core.video import Frame, VideoStream
from sentinel_core.video.detect import Detector


class OpenCVVideoStream(VideoStream):
    """
    An OpenCV raw video stream.
    """

    def __init__(self, source: int | str):
        self._capture: cv2.VideoCapture = cv2.VideoCapture(source)

    async def next_frame(self) -> Optional[Frame]:
        has_next: bool
        data: np.ndarray

        loop = asyncio.get_event_loop()

        has_next = await loop.run_in_executor(None, self._capture.grab)
        if not has_next:  # No frame data
            return None

        _, data = await loop.run_in_executor(None, self._capture.retrieve)

        timestamp: float = await loop.run_in_executor(
            None, self._capture.get, cv2.CAP_PROP_POS_MSEC
        )

        return Frame(timestamp, data)

    async def destroy(self) -> None:
        """
        Cleans up the resources associated with this OpenCV video stream.

        This method should be called once the stream is no longer needed.
        Alternatively, use an `async with` statement to automatically perform the clean-up.
        """
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._capture.release)

    # For use with `async with` statements.
    async def __aenter__(self) -> Self:
        return self

    # For use with `async with` statements.
    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        await self.destroy()


_opencv_video_stream_descriptor = ComponentDescriptor(
    display_name="OpenCV",
    kind=ComponentKind.VideoStream,
    cls=OpenCVVideoStream,
    args=(
        ComponentArgDescriptor(
            display_name="Source",
            arg_name="source",
            option_type=str,
            required=True,
            default=None,
            # TODO: add transform
        ),
    ),
)


class OpenCVPlugin(Plugin):
    components = [_opencv_video_stream_descriptor]
