from collections.abc import Iterable
from enum import Enum, auto

import ultralytics
from sentinel_core.alert import Subscriber
from sentinel_core.plugins import Plugin
from sentinel_core.video import Frame, VideoStream
from sentinel_core.video.detect import (BoundingBox, Detection,
                                        DetectionResult, Detector,
                                        PredictedCategory)


class ModelType(Enum):
    YOLO = auto()
    SAM = auto()
    FastSAM = auto()
    YOLO_NAS = auto()
    RT_DETR = auto()
    YOLO_WORLD = auto()

    def to_model_class(self):
        if self == ModelType.YOLO:
            return ultralytics.YOLO
        elif self == ModelType.SAM:
            return ultralytics.SAM
        elif self == ModelType.FastSAM:
            return ultralytics.FastSAM
        elif self == ModelType.YOLO_NAS:
            return ultralytics.NAS
        elif self == ModelType.RT_DETR:
            return ultralytics.RT_DETR
        elif self == ModelType.YOLO_WORLD:
            return ultralytics.YOLO_WORLD
        else:
            raise AssertionError("Unreachable code")


class UltralyticsDetector(Detector):
    def __init__(self, model_type: str | ModelType, model_path: str):
        if isinstance(model_type, str):
            try:
                model_type = ModelType[model_type]
            except KeyError:
                raise ValueError(
                    f"Invalid model type '{model_type}' — "
                    f"valid types are: {", ".join(variant.name for variant in ModelType)}"
                )

        model_class = model_type.to_model_class()
        self._model = model_class(model_path)

    async def detect(self, frame: Frame) -> DetectionResult:
        detections = []
        results = self._model(frame.data, verbose=False)
        for result in results:
            boxes = result.boxes
            for (cls, conf, xywh) in zip(boxes.cls, boxes.conf, boxes.xywh):
                cls_str = result.names[int(cls.item())]

                pred_categories = [PredictedCategory(cls_str, conf.item())]
                bounding_box = BoundingBox(
                    int(xywh[0].item()),  # x
                    int(xywh[1].item()),  # y
                    int(xywh[2].item()),  # w
                    int(xywh[3].item()),  # h
                )
                detections.append(Detection(pred_categories, bounding_box))

        return DetectionResult(frame.timestamp or -1, frame, detections)


class UltralyticsPlugin(Plugin):
    name = "Ultralytics"
    video_stream_classes: Iterable[type[VideoStream]] = set()
    detector_classes: Iterable[type[Detector]] = {UltralyticsDetector}
    subscriber_classes: Iterable[type[Subscriber]] = set()
