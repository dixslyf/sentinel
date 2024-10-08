import math
from asyncio import Queue
from typing import Any

from aioreactive import AsyncObserver

from sentinel.alert import Alert, RawEmitter, ThreatLevel
from sentinel.video import VideoStream
from sentinel.video.detect import DetectionResult, Detector


class VideoDetectionAlert(Alert):
    def __init__(
        self,
        stream: VideoStream,
        detector: Detector,
        detection_result: DetectionResult,
        threat_level: ThreatLevel,
    ):
        self._stream = stream
        self._detector = detector
        self._detection_result = detection_result
        self._threat_level = threat_level

    @property
    def header(self) -> str:
        return "Video Detection Alert"

    @property
    def description(self) -> str:
        desc = f"Source: {self._stream.name}, "
        desc += f"Threat Level: {self._threat_level}, "
        for detection in self._detection_result.detections:
            # Choose the most likely object category.
            object_cat = max(
                detection.pred_categories,
                key=lambda cat: cat.score if cat.score is not None else -math.inf,
            )
            desc += f"Detected: {object_cat.name}, "
        return desc

    @property
    def threat_level(self) -> ThreatLevel:
        return self._threat_level

    @property
    def data(self) -> dict[str, Any]:
        return {
            "stream": self._stream,
            "detector": self._detector,
            "detection_result": self._detection_result,
        }


class VideoDetectorAlertEmitter(RawEmitter, AsyncObserver[DetectionResult]):
    # TODO: Ideally, there should be a mechanism to follow the chain of messages
    # to the source detector and video stream.
    def __init__(self, stream: VideoStream, detector: Detector):
        self._stream = stream
        self._detector = detector
        self._queue: Queue = Queue()

    async def next_alert(self) -> Alert:
        alert = await self._queue.get()
        self._queue.task_done()
        return alert

    async def asend(self, dr: DetectionResult):
        if not dr.detections:
            return

        alert = VideoDetectionAlert(
            self._stream, self._detector, dr, ThreatLevel.Unknown
        )
        await self._queue.put(alert)

    async def athrow(self, error: Exception):
        raise error

    async def aclose(self):
        pass
