import asyncio
from collections.abc import Iterable
from typing import Optional, Self

import cv2
import numpy as np
from sentinel_core.alert import Subscriber
from sentinel_core.plugins import Plugin
from sentinel_core.video import Frame, VideoStream
from sentinel_core.video.detect import Detector


class OpenCVVideoStream(VideoStream):
    """
    An OpenCV raw video stream.
    """

    def __init__(self, capture: cv2.VideoCapture):
        if not capture.isOpened():
            raise ValueError(
                "OpenCV video capture has not been or failed to initialise."
            )

        self._capture: cv2.VideoCapture = capture

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


class OpenCVPlugin(Plugin):
    name = "OpenCV"
    video_stream_classes: Iterable[type[VideoStream]] = {OpenCVVideoStream}
    detector_classes: Iterable[type[Detector]] = set()
    subscriber_classes: Iterable[type[Subscriber]] = set()
