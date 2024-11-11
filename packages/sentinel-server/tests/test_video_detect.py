import numpy as np
import pytest
from sentinel_core.video import Frame
from sentinel_core.video.detect import (
    BoundingBox,
    Detection,
    DetectionResult,
    PredictedCategory,
)

from sentinel_server.video.detect import visualise_detections


@pytest.fixture
def sample_frame():
    # Create a blank image (black frame)
    height, width = 480, 640
    data = np.zeros((height, width, 3), dtype=np.uint8)
    return Frame(data=data)


@pytest.fixture
def sample_detection_result(sample_frame):
    bbox = BoundingBox(x=50, y=50, width=100, height=150)
    pred_category = PredictedCategory(name="Person", score=0.95)
    detection = Detection(pred_categories=[pred_category], bounding_box=bbox)
    return DetectionResult(frame=sample_frame, detections=[detection])


def test_visualise_detections(sample_detection_result):
    frame_with_detections = visualise_detections(sample_detection_result)

    # Check if the bounding box is drawn.
    # We don't check every single pixel that should have been drawn on
    # since that is difficult to determine. We just check that at least
    # one pixel has been turned red.
    bbox = sample_detection_result.detections[0].bounding_box
    red_channel = frame_with_detections.data[
        bbox.y : bbox.y + bbox.height, bbox.x : bbox.x + bbox.width, 0
    ]
    assert np.any(red_channel == 255), "Bounding box not drawn correctly"

    # Check if the text is drawn. Since we can't predict exactly on which
    # pixels the text will be drawn, we just check that at least one pixel
    # has been drawn on within the text region.
    text_position = (10 + bbox.x, 20 + bbox.y)
    text_region = frame_with_detections.data[
        text_position[1] - 5 : text_position[1] + 5,
        text_position[0] - 5 : text_position[0] + 5,
    ]
    assert np.any(text_region[:, :, 0] == 255), "Text not drawn correctly"


def test_visualise_detections_no_score(sample_frame):
    bbox = BoundingBox(x=50, y=50, width=100, height=150)
    pred_category = PredictedCategory(name="Person", score=None)
    detection = Detection(pred_categories=[pred_category], bounding_box=bbox)
    detection_result = DetectionResult(frame=sample_frame, detections=[detection])

    frame_with_detections = visualise_detections(detection_result)

    # Check if the bounding box is drawn.
    # We don't check every single pixel that should have been drawn on
    # since that is difficult to determine. We just check that at least
    # one pixel has been turned red.
    red_channel = frame_with_detections.data[
        bbox.y : bbox.y + bbox.height, bbox.x : bbox.x + bbox.width, 0
    ]
    assert np.any(red_channel == 255), "Bounding box not drawn correctly"

    # Check if the text is drawn. Since we can't predict exactly on which
    # pixels the text will be drawn, we just check that at least one pixel
    # has been drawn on within the text region.
    text_position = (10 + bbox.x, 20 + bbox.y)
    text_region = frame_with_detections.data[
        text_position[1] - 5 : text_position[1] + 5,
        text_position[0] - 5 : text_position[0] + 5,
    ]
    assert np.any(text_region[:, :, 0] == 255), "Text not drawn correctly"
