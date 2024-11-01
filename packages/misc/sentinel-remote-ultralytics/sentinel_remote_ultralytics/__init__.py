import base64
from argparse import ArgumentParser, Namespace
from typing import Any

import litserve
import numpy as np
from sentinel_core.video import Frame
from sentinel_core.video.detect import DetectionResult
from sentinel_ultralytics import ModelType, UltralyticsDetector


class UltralyticsLitserveAPI(litserve.LitAPI):
    def __init__(self, model_type: ModelType, model_path: str):
        self.model_type = model_type
        self.model_path = model_path

    def setup(self, device):
        self.detector = UltralyticsDetector(self.model_type, self.model_path)

    def decode_request(self, request: dict[str, Any]) -> Frame:
        frame_bytes = base64.b64decode(request["frame_base64"])
        frame_data = np.frombuffer(frame_bytes, dtype=request["dtype"]).reshape(
            request["shape"]
        )
        return Frame(frame_data)

    def predict(self, frame: Frame) -> DetectionResult:
        return self.detector.detect(frame)

    def encode_response(self, dr: DetectionResult):
        detections = [detection.to_dict() for detection in dr.detections]
        return {"detections": detections}


def parse_args() -> Namespace:
    parser = ArgumentParser()

    parser.add_argument(
        "model_type",
        metavar="model-type",
        type=str,
        help="The type of the Ultralytics model",
        choices=[model_type.name for model_type in ModelType],
    )

    parser.add_argument(
        "model_path",
        metavar="model-path",
        type=str,
        help="The path to the Ultralytics model",
    )

    parser.add_argument(
        "-p",
        "--port",
        type=int,
        help="The port to serve on",
        default=8000,
    )

    return parser.parse_args()


def entry() -> None:
    args = parse_args()

    model_type = ModelType[args.model_type]
    server = litserve.LitServer(
        UltralyticsLitserveAPI(model_type, args.model_path),
        accelerator="auto",
    )
    server.run(port=args.port)
