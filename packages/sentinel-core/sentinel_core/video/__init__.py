from dataclasses import dataclass
from typing import Optional, Protocol

import numpy as np


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


class AsyncVideoStream(Protocol):
    """
    Protocol for asynchronous video streams.
    """

    async def next_frame(self) -> Optional[Frame]:
        """
        Returns the next video frame or `None` if no frame data is available.
        """

    async def clean_up(self) -> None:
        """
        Cleans up any resources associated with the video stream.
        """


class SyncVideoStream(Protocol):
    """
    Protocol for synchronous video streams.
    """

    def next_frame(self) -> Optional[Frame]:
        """
        Returns the next video frame or `None` if no frame data is available.
        """

    def clean_up(self) -> None:
        """
        Cleans up any resources associated with the video stream.
        """


class VideoStreamNoDataException(Exception):
    """
    An exception raised when a video stream has no data.
    """
