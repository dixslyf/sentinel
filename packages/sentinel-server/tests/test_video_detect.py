import asyncio

import numpy as np
import pytest
from sentinel_core.video import AsyncVideoStream, Frame, VideoStreamNoDataException
from sentinel_core.video.detect import (
    AsyncDetector,
    BoundingBox,
    Detection,
    DetectionResult,
    PredictedCategory,
)

from sentinel_server.video import ReactiveVideoStream
from sentinel_server.video.detect import ReactiveDetector, visualise_detections


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


@pytest.mark.asyncio
async def test_reactive_detector_asend(mocker, sample_detection_result):
    async_detector_mock = mocker.AsyncMock(spec=AsyncDetector)
    async_detector_mock.detect.return_value = sample_detection_result
    reactive_detector = ReactiveDetector(async_detector_mock)

    results = []

    async def observer(result):
        results.append(result)

    await reactive_detector.subscribe_async(observer)
    await reactive_detector.asend(sample_detection_result.frame)

    assert len(results) == 1
    assert results[0] == sample_detection_result


@pytest.mark.asyncio
async def test_reactive_detector_aclose(mocker):
    async_detector_mock = mocker.AsyncMock(spec=AsyncDetector)
    reactive_detector = ReactiveDetector(async_detector_mock)

    await reactive_detector.aclose()
    async_detector_mock.clean_up.assert_called_once()


class MockVideoStream(AsyncVideoStream):
    def __init__(self, frames):
        self.frames = frames
        self.index = 0

    async def next_frame(self):
        if self.index < len(self.frames):
            frame = self.frames[self.index]
            self.index += 1
            return frame
        else:
            await asyncio.sleep(0.1)  # Simulate waiting for the next frame
            return None

    async def clean_up(self):
        pass


@pytest.mark.asyncio
async def test_reactive_video_stream_start_stop(sample_frame):
    mock_stream = MockVideoStream([sample_frame] * 5)
    reactive_stream = ReactiveVideoStream(mock_stream)

    frames = []

    async def observer(frame):
        frames.append(frame)

    await reactive_stream.subscribe_async(observer)
    task = asyncio.create_task(reactive_stream.start())
    await asyncio.sleep(0.5)  # Let the stream run for a short time
    await reactive_stream.stop()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    assert len(frames) == 5, "Expected 5 frames to be emitted"
