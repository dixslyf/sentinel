from enum import Enum, auto

import ultralytics
from sentinel_core.plugins import (
    Choice,
    ComponentArgDescriptor,
    ComponentDescriptor,
    ComponentKind,
    Plugin,
)
from sentinel_core.video import Frame
from sentinel_core.video.detect import (
    BoundingBox,
    Detection,
    DetectionResult,
    PredictedCategory,
    SyncDetector,
)


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


class UltralyticsDetector(SyncDetector):
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

    def detect(self, frame: Frame) -> DetectionResult:
        detections = []
        results = self._model(frame.data, verbose=False)
        for result in results:
            boxes = result.boxes
            for cls, conf, xywh in zip(boxes.cls, boxes.conf, boxes.xywh):
                cls_str = result.names[int(cls.item())]

                pred_categories = [PredictedCategory(cls_str, conf.item())]

                # The x and y coordinates from the model are the center point
                # of the bounding box, not the top corner that we want,
                # so we need to do a bit of math.
                x = xywh[0].item()
                y = xywh[1].item()
                w = xywh[2].item()
                h = xywh[3].item()
                bounding_box = BoundingBox(
                    int(x - w / 2), int(y - h / 2), int(w), int(h)
                )
                detections.append(Detection(pred_categories, bounding_box))

        return DetectionResult(frame, detections)


_ultralytics_detector_descriptor = ComponentDescriptor(
    display_name="Ultralytics",
    kind=ComponentKind.SyncDetector,
    cls=UltralyticsDetector,
    args=(
        ComponentArgDescriptor(
            display_name="Model Type",
            arg_name="model_type",
            option_type=str,
            required=True,
            default=None,
            choices=frozenset(
                (
                    Choice.from_string("YOLO"),
                    Choice.from_string("SAM"),
                    Choice.from_string("FastSAM"),
                    Choice.from_string("YOLO_NAS"),
                    Choice.from_string("RT_DETR"),
                    Choice.from_string("YOLO_WORLD"),
                )
            ),
        ),
        ComponentArgDescriptor(
            display_name="Model Path",
            arg_name="model_path",
            option_type=str,
            required=True,
            default=None,
            # TODO: add a validator
        ),
    ),
)


plugin = Plugin(frozenset({_ultralytics_detector_descriptor}))
