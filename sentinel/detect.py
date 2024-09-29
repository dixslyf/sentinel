import typing
from abc import abstractmethod
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Optional, Protocol, Self

import cv2
import mediapipe as mp

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


class AsyncDetector(Protocol):
    """
    Protocol for asynchronous object detectors.
    """

    @abstractmethod
    def detect_async(self, frame: Frame) -> None:
        """
        Detects objects in the given frame asynchronously.

        Implementors should use a callback mechanism to communicate results.
        """


class MediaPipeAsyncDetector:
    def __init__(
        self,
        mp_detector_opts: mp.tasks.vision.ObjectDetectorOptions,
    ):
        self._last_result: Optional[tuple[Frame, Sequence[Detection]]]
        self._mp_detector: mp.tasks.vision.ObjectDetector

        # Force live stream mode.
        mp_detector_opts.running_mode = mp.tasks.vision.RunningMode.LIVE_STREAM

        # Wrap the callback to save the last result for easy retrieval.
        self._last_result = None
        wrapped_callback = mp_detector_opts.result_callback

        def result_callback(result, image, ts):
            # Update the last result.
            self._last_result = (
                Frame(ts, image.numpy_view()),
                [Detection.from_mediapipe(det) for det in result.detections],
            )

            # Call the wrapped callback.
            if wrapped_callback is not None:
                wrapped_callback(result, image, ts)

        mp_detector_opts.result_callback = result_callback

        self._mp_detector = mp.tasks.vision.ObjectDetector.create_from_options(
            mp_detector_opts
        )

    def detect_async(self, frame: Frame) -> None:
        if frame.timestamp is None:
            raise ValueError(
                "MediaPipeAsyncDetector can only handle frames with timestamps."
            )

        ts = int(typing.cast(float, frame.timestamp))

        # MediaPipe has its own `Image` class.
        # We can simply pass the frame data to the constructor.
        # TODO: how to handle varying image formats?
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame.data)

        self._mp_detector.detect_async(mp_image, ts)

    def last_result(self) -> Optional[tuple[Frame, Sequence[Detection]]]:
        """
        Returns the last detection results.
        """
        return self._last_result

    # For use with `with` statements.
    def __enter__(self):
        return self

    # For use with `with` statements.
    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self._mp_detector.__exit__(exc_type, exc_value, traceback)


def visualise_detections(frame: Frame, detections: Iterable) -> Frame:
    for detection in detections:
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
