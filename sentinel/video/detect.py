import asyncio
import typing
from asyncio import Future
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Optional, Protocol, Self

import cv2
import mediapipe as mp
import numpy as np
from aioreactive import AsyncObservable, AsyncObserver, AsyncSubject

from sentinel.video import Frame


@dataclass
class BoundingBox:
    x: int
    y: int
    width: int
    height: int

    @classmethod
    def from_mediapipe(
        cls, mp_bounding_box: mp.tasks.components.containers.BoundingBox
    ) -> Self:
        return cls(
            mp_bounding_box.origin_x,
            mp_bounding_box.origin_y,
            mp_bounding_box.width,
            mp_bounding_box.height,
        )


@dataclass
class PredictedCategory:
    name: str
    score: Optional[float]

    @classmethod
    def from_mediapipe(
        cls, mp_category: mp.tasks.components.containers.Category
    ) -> Self:
        return cls(mp_category.category_name, mp_category.score)


@dataclass
class Detection:
    pred_categories: Sequence[PredictedCategory]
    bounding_box: BoundingBox

    @classmethod
    def from_mediapipe(
        cls, mp_detection: mp.tasks.components.containers.Detection
    ) -> Self:
        return cls(
            [PredictedCategory.from_mediapipe(cat) for cat in mp_detection.categories],
            BoundingBox.from_mediapipe(mp_detection.bounding_box),
        )


@dataclass
class DetectionResult:
    timestamp: float
    frame: Frame
    detections: Sequence[Detection]


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


class RawDetector(Protocol):
    """
    Protocol for raw object detectors.
    """

    async def detect(self, frame: Frame) -> DetectionResult:
        """
        Detects objects in the given frame asynchronously.
        """


class Detector(AsyncObservable[DetectionResult], AsyncObserver[Frame]):
    def __init__(self, raw_detector: RawDetector):
        self._raw_detector: RawDetector = raw_detector
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


class MediaPipeRawDetector(RawDetector):
    def __init__(
        self,
        mp_detector_opts: mp.tasks.vision.ObjectDetectorOptions,
    ):
        self._mp_detector: mp.tasks.vision.ObjectDetector

        # Force live stream mode.
        mp_detector_opts.running_mode = mp.tasks.vision.RunningMode.LIVE_STREAM

        # Dictionary of timestamps to futures.
        # Each call to `detect_async()` will create a future in this dictionary
        # with the timestamp as the key.
        self._futures: dict[int, Future[DetectionResult]] = {}

        # Wrap the callback to set the results in the corresponding future.
        # Note that MediaPipe seems to run the callback in a separate thread.
        wrapped_callback = mp_detector_opts.result_callback

        def result_callback(
            result: mp.tasks.components.containers.DetectionResult,
            image: mp.Image,
            timestamp: int,
        ):
            # Set the value in the corresponding future.
            # It is expected that `self.detect_async()` will have already created the future.
            fut = self._futures[timestamp]

            # MediaPipe seems to run the callback in a separate thread,
            # so we need to use `call_soon_threadsafe()`.
            fut.get_loop().call_soon_threadsafe(
                fut.set_result,
                DetectionResult(
                    timestamp,
                    Frame(timestamp, image.numpy_view()),
                    [Detection.from_mediapipe(det) for det in result.detections],
                ),
            )

            # Since the future's value has been set, we don't need to keep track of it anymore.
            self._futures.pop(timestamp)

            # Call the wrapped callback.
            if wrapped_callback is not None:
                wrapped_callback(result, image, timestamp)

        mp_detector_opts.result_callback = result_callback

        self._mp_detector = mp.tasks.vision.ObjectDetector.create_from_options(
            mp_detector_opts
        )

    async def detect(self, frame: Frame) -> DetectionResult:
        if frame.timestamp is None:
            raise ValueError(
                "MediaPipeAsyncDetector can only handle frames with timestamps."
            )

        ts = int(typing.cast(float, frame.timestamp))

        # MediaPipe has its own `Image` class.
        # We can simply pass the frame data to the constructor.
        # TODO: how to handle varying image formats?
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame.data)

        # Create a future for the results.
        # The callback created in `__init__()` will set the future's value
        # when the detection is done.
        loop = asyncio.get_event_loop()
        fut = loop.create_future()
        self._futures[ts] = fut

        self._mp_detector.detect_async(mp_image, ts)

        return await fut

    # For use with `async with` statements.
    async def __aenter__(self) -> Self:
        return self

    # For use with `async with` statements.
    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.__exit__, exc_type, exc_value, traceback)

    # For use with `with` statements.
    def __enter__(self):
        return self

    # For use with `with` statements.
    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self._mp_detector.__exit__(exc_type, exc_value, traceback)
