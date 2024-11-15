import base64

import aiohttp
from sentinel_core.plugins import (
    ComponentArgDescriptor,
    ComponentDescriptor,
    ComponentKind,
    Plugin,
)
from sentinel_core.video import Frame
from sentinel_core.video.detect import AsyncDetector, Detection, DetectionResult


class RemoteDetector(AsyncDetector):
    def __init__(self, url: str):
        self._url = url
        self._session = aiohttp.ClientSession()

    async def detect(self, frame: Frame) -> DetectionResult:
        data = {
            "frame_base64": base64.b64encode(frame.data.tobytes()).decode("utf-8"),
            "dtype": str(frame.data.dtype),
            "shape": frame.data.shape,
        }

        async with self._session.post(self._url, json=data) as response:
            json_dict = await response.json()
            detections = Detection.schema().load(json_dict["detections"], many=True)
            return DetectionResult(frame, detections)

    async def clean_up(self) -> None:
        await self._session.close()


_remote_detector_descriptor = ComponentDescriptor(
    display_name="Remote Detector",
    kind=ComponentKind.AsyncDetector,
    cls=RemoteDetector,
    args=(
        ComponentArgDescriptor(
            display_name="URL",
            arg_name="url",
            option_type=str,
            required=True,
            default=None,
        ),
    ),
)


plugin = Plugin(frozenset({_remote_detector_descriptor}))
