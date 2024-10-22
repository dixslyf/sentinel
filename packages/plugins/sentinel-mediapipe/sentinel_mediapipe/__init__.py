import asyncio
import typing
from asyncio import Future
from collections.abc import Iterable
from typing import Self

import mediapipe as mp
from sentinel_core.alert import Subscriber
from sentinel_core.plugins import Plugin
from sentinel_core.video import Frame, VideoStream
from sentinel_core.video.detect import (
    BoundingBox,
    Detection,
    DetectionResult,
    Detector,
    PredictedCategory,
)


def bounding_box_from_mp(
    mp_bounding_box: mp.tasks.components.containers.BoundingBox,
) -> BoundingBox:
    return BoundingBox(
        mp_bounding_box.origin_x,
        mp_bounding_box.origin_y,
        mp_bounding_box.width,
        mp_bounding_box.height,
    )


def predicted_category_from_mp(
    mp_category: mp.tasks.components.containers.Category,
) -> PredictedCategory:
    return PredictedCategory(mp_category.category_name, mp_category.score)


def detection_from_mp(
    mp_detection: mp.tasks.components.containers.Detection,
) -> Detection:
    return Detection(
        [predicted_category_from_mp(cat) for cat in mp_detection.categories],
        bounding_box_from_mp(mp_detection.bounding_box),
    )


class MediaPipeDetector(Detector):
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
            timestamp: mp.Timestamp,
        ):
            ts = timestamp.value / 1000
            # Set the value in the corresponding future.
            # It is expected that `self.detect_async()` will have already created the future.
            fut = self._futures[ts]

            # MediaPipe seems to run the callback in a separate thread,
            # so we need to use `call_soon_threadsafe()`.
            fut.get_loop().call_soon_threadsafe(
                fut.set_result,
                DetectionResult(
                    ts,
                    Frame(ts, image.numpy_view()),
                    [detection_from_mp(det) for det in result.detections],
                ),
            )

            # Since the future's value has been set, we don't need to keep track of it anymore.
            self._futures.pop(ts)

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


class MediaPipePlugin(Plugin):
    name = "MediaPipe"
    video_stream_classes: Iterable[type[VideoStream]] = set()
    detector_classes: Iterable[type[Detector]] = {MediaPipeDetector}
    subscriber_classes: Iterable[type[Subscriber]] = set()
