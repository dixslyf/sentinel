from collections.abc import Sequence
from dataclasses import dataclass
from typing import Optional, Protocol

from sentinel_core.video import Frame


@dataclass
class BoundingBox:
    x: int
    y: int
    width: int
    height: int


@dataclass
class PredictedCategory:
    name: str
    score: Optional[float]


@dataclass
class Detection:
    pred_categories: Sequence[PredictedCategory]
    bounding_box: BoundingBox


@dataclass
class DetectionResult:
    frame: Frame
    detections: Sequence[Detection]


class AsyncDetector(Protocol):
    """
    Protocol for raw asynchronous object detectors.
    """

    async def detect(self, frame: Frame) -> DetectionResult:
        """
        Detects objects in the given frame asynchronously.
        """

    async def clean_up(self) -> None:
        """
        Cleans up any resources associated with this detector.
        """


class SyncDetector(Protocol):
    """
    Protocol for raw synchronous object detectors.
    """

    def detect(self, frame: Frame) -> DetectionResult:
        """
        Detects objects in the given frame synchronously.
        """

    def clean_up(self) -> None:
        """
        Cleans up any resources associated with this detector.
        """
