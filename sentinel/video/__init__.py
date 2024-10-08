import asyncio
from dataclasses import dataclass
from typing import Optional, Protocol, Self

import cv2
import numpy as np
from aioreactive import AsyncObservable, AsyncObserver, AsyncSubject


@dataclass
class Frame:
    """
    Stores data about a single video frame.

    Attributes:
        timestamp: The timestamp of the frame in milliseconds.
        data: The frame data as a NumPy `ndarray`.
    """

    timestamp: Optional[float]
    data: np.ndarray


class VideoStream(Protocol):
    """
    Protocol for raw video streams.
    """

    async def next_frame(self) -> Optional[Frame]:
        """
        Returns the next video frame or `None` if no frame data is available.
        """


class VideoStreamNoDataException(Exception):
    """
    An exception raised when a video stream has no data.
    """


class ReactiveVideoStream(AsyncObservable[Frame]):
    def __init__(self, name: str, raw_stream: VideoStream):
        self._name: str = name
        self._raw_stream: VideoStream = raw_stream
        self._run: bool = False
        self._subject: AsyncSubject[Frame] = AsyncSubject()

    @property
    def name(self) -> str:
        return self._name

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


class OpenCVViewer(AsyncObserver[Frame]):
    def __init__(self, win_name: str):
        self._win_name = win_name

    async def asend(self, frame: Frame):
        cv2.imshow(self._win_name, frame.data)

    async def athrow(self, error):
        cv2.destroyWindow(self._win_name)

    async def aclose(self):
        cv2.destroyWindow(self._win_name)
