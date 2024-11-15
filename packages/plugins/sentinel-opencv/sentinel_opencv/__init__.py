from typing import Any, Optional

import cv2
import numpy as np
from sentinel_core.plugins import (
    ComponentArgDescriptor,
    ComponentDescriptor,
    ComponentKind,
    Plugin,
)
from sentinel_core.video import Frame, SyncVideoStream


class OpenCVVideoStream(SyncVideoStream):
    """
    An OpenCV raw video stream.
    """

    def __init__(self, source: int | str, buffer_size: int = 1):
        self._capture: cv2.VideoCapture = cv2.VideoCapture(source)
        self._capture.set(cv2.CAP_PROP_BUFFERSIZE, buffer_size)

    def next_frame(self) -> Optional[Frame]:
        has_next: bool
        data: np.ndarray

        has_next = self._capture.grab()
        if not has_next:  # No frame data
            return None

        _, data = self._capture.retrieve()

        # OpenCV uses BGR by default. However, most other libraries
        # and applications expect RGB, so we convert to RGB.
        data = cv2.cvtColor(data, cv2.COLOR_BGR2RGB)

        return Frame(data)

    def clean_up(self) -> None:
        """
        Cleans up the resources associated with this OpenCV video stream.

        This method should be called once the stream is no longer needed.
        Alternatively, use an `async with` statement to automatically perform the clean-up.
        """
        self._capture.release()


def args_transform(kwargs: dict[str, Any]) -> dict[str, Any]:
    # Check if source can be converted into an integer.
    # If it can, convert it.
    source = kwargs["source"]
    try:
        source_int = int(source)
        new_kwargs = kwargs.copy()
        new_kwargs["source"] = source_int
        return new_kwargs
    except ValueError:
        return kwargs


_opencv_video_stream_descriptor = ComponentDescriptor(
    display_name="OpenCV",
    kind=ComponentKind.SyncVideoStream,
    cls=OpenCVVideoStream,
    args=(
        ComponentArgDescriptor(
            display_name="Source",
            arg_name="source",
            option_type=str,
            required=True,
            default=None,
        ),
    ),
    args_transform=args_transform,
)


plugin = Plugin(frozenset({_opencv_video_stream_descriptor}))
