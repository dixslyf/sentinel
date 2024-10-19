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
