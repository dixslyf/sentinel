import time
from typing import Self

import cv2
import numpy as np
from aioreactive import AsyncObservable, AsyncObserver, AsyncSubject
from sentinel_core.video import Frame
from sentinel_core.video.detect import AsyncDetector, DetectionResult, SyncDetector

import sentinel_server.tasks


def visualise_detections(detection_result: DetectionResult) -> Frame:
    """
    Visualises the detections onto the detection result's frame.

    Note that this function will modify the frame in-place. To avoid mutation,
    make a copy of the frame before passing the detection result to this function.
    """
    frame = detection_result.frame
    for detection in detection_result.detections:
        # Draw a red bounding box.
        bbox = detection.bounding_box
        start_point = bbox.x, bbox.y
        end_point = bbox.x + bbox.width, bbox.y + bbox.height
        cv2.rectangle(frame.data, start_point, end_point, (255, 0, 0), 3)

        # Draw the first category and score.
        pred_category = detection.pred_categories[0]
        score_display = str(
            round(pred_category.score, 2) if pred_category.score is not None else None
        )
        result_text = pred_category.name + " (" + score_display + ")"
        cv2.putText(
            frame.data,
            result_text,
            (10 + bbox.x, 20 + bbox.y),
            cv2.FONT_HERSHEY_DUPLEX,
            1,
            (255, 0, 0),  # Red
            1,
        )

    return frame


class ReactiveDetectionVisualiser(
    AsyncObservable[Frame], AsyncObserver[DetectionResult]
):
    def __init__(self, inplace: bool = False):
        self._subject_out: AsyncSubject[Frame] = AsyncSubject()
        self._inplace = inplace

    async def subscribe_async(self, observer):
        return await self._subject_out.subscribe_async(observer)

    async def asend(self, dr: DetectionResult):
        if not self._inplace:
            # Make a copy of the frame
            frame_data_cp = np.copy(dr.frame.data)
            frame_cp = Frame(frame_data_cp)
            dr = DetectionResult(frame_cp, dr.detections)

        frame = visualise_detections(dr)
        await self._subject_out.asend(frame)

    async def athrow(self, error: Exception):
        await self._subject_out.athrow(error)

    async def aclose(self):
        await self._subject_out.aclose()


class ReactiveDetector(AsyncObservable[DetectionResult], AsyncObserver[Frame]):
    def __init__(self, raw_detector: AsyncDetector, interval: float = 1):
        self._raw_detector: AsyncDetector = raw_detector
        self._time_last: float = 0
        self._interval: float = interval

        self._subject_out: AsyncSubject[DetectionResult] = AsyncSubject()

    @classmethod
    def from_sync_detector(cls, raw_detector: SyncDetector) -> Self:
        async_detector = AsyncDetectorWrapper(raw_detector)
        return cls(async_detector)

    async def subscribe_async(self, observer):
        return await self._subject_out.subscribe_async(observer)

    async def asend(self, frame: Frame):
        cur_time = time.time()
        if cur_time >= self._time_last + self._interval:
            self._time_last = cur_time
            detection_result = await self._raw_detector.detect(frame)
        else:
            # Create dummy detection result.
            detection_result = DetectionResult(frame, [])
        await self._subject_out.asend(detection_result)

    async def athrow(self, error: Exception):
        await self._subject_out.athrow(error)

    async def aclose(self):
        await self._subject_out.aclose()


class AsyncDetectorWrapper(AsyncDetector):
    """
    A wrapper around a synchronous detector to make it asynchronous.
    """

    def __init__(self, sync_detector: SyncDetector):
        self._sync_detector: SyncDetector = sync_detector

    async def detect(self, frame: Frame) -> DetectionResult:
        return await sentinel_server.tasks.run_in_thread(
            self._sync_detector.detect, frame
        )
