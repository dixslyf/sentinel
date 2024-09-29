from abc import abstractmethod
from dataclasses import dataclass
from typing import Optional, Protocol, Self

import cv2
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


class VideoSource(Protocol):
    """
    Protocol for video sources.
    """

    @abstractmethod
    def next_frame(self) -> Optional[Frame]:
        """
        Returns the next video frame or `None` if no frame data is available.
        """


class OpenCVVideoSource(VideoSource):
    """
    An OpenCV video source.
    """

    def __init__(self, capture: cv2.VideoCapture):
        if not capture.isOpened():
            raise ValueError(
                "OpenCV video capture has not been or failed to initialise."
            )

        self._capture: cv2.VideoCapture = capture

    def next_frame(self) -> Optional[Frame]:
        has_next: bool
        data: np.ndarray

        has_next, data = self._capture.read()
        if not has_next:  # No frame data
            return None

        timestamp: float = self._capture.get(cv2.CAP_PROP_POS_MSEC)
        return Frame(timestamp, data)

    def destroy(self) -> None:
        """
        Cleans up the resources associated with this video source.

        This method should be called once the `OpenCVVideoSource` object is no longer needed.
        Alternatively, use a `with` statement to automatically perform the clean-up.
        """
        self._capture.release()

    # For use with `with` statements.
    def __enter__(self) -> Self:
        return self

    # For use with `with` statements.
    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.destroy()
