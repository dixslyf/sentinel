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
    timestamp: float
    frame: Frame
    detections: Sequence[Detection]


class Detector(Protocol):
    """
    Protocol for raw object detectors.
    """

    async def detect(self, frame: Frame) -> DetectionResult:
        """
        Detects objects in the given frame asynchronously.
        """
