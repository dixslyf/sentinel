import asyncio
import typing
from asyncio import Future
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Optional, Protocol, Self

import cv2
import numpy as np
from aioreactive import AsyncObservable, AsyncObserver, AsyncSubject
from sentinel_core.video import Frame
from sentinel_core.video.detect import DetectionResult, Detector


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


class DetectionResultVisualiser(AsyncObservable[Frame], AsyncObserver[DetectionResult]):
    def __init__(self, inplace: bool = False):
        self._subject_out: AsyncSubject[Frame] = AsyncSubject()
        self._inplace = inplace

    async def subscribe_async(self, observer):
        return await self._subject_out.subscribe_async(observer)

    async def asend(self, dr: DetectionResult):
        if not self._inplace:
            # Make a copy of the frame
            frame_data_cp = np.copy(dr.frame.data)
            frame_cp = Frame(dr.frame.timestamp, frame_data_cp)
            dr = DetectionResult(dr.timestamp, frame_cp, dr.detections)

        frame = visualise_detections(dr)
        await self._subject_out.asend(frame)

    async def athrow(self, error: Exception):
        await self._subject_out.athrow(error)

    async def aclose(self):
        await self._subject_out.aclose()


class ReactiveDetector(AsyncObservable[DetectionResult], AsyncObserver[Frame]):
    def __init__(self, raw_detector: Detector):
        self._raw_detector: Detector = raw_detector
        self._subject_out: AsyncSubject[DetectionResult] = AsyncSubject()

    async def subscribe_async(self, observer):
        return await self._subject_out.subscribe_async(observer)

    async def asend(self, frame: Frame):
        detection_result = await self._raw_detector.detect(frame)
        await self._subject_out.asend(detection_result)

    async def athrow(self, error: Exception):
        await self._subject_out.athrow(error)

    async def aclose(self):
        await self._subject_out.aclose()
