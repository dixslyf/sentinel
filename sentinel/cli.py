import asyncio
from argparse import ArgumentParser, Namespace

import cv2
import mediapipe as mp

from sentinel.alert import Manager
from sentinel.alert.filters import Cooldown
from sentinel.alert.subscribers import DesktopNotificationSubscriber
from sentinel.alert.video import VideoDetectorAlertEmitter
from sentinel.plugins import discover_plugins
from sentinel.video import OpenCVRawVideoStream, OpenCVViewer, VideoStream
from sentinel.video.detect import (
    DetectionResultVisualiser,
    Detector,
    MediaPipeRawDetector,
)

# MediaPipe has a weird way of importing stuff.
BaseOptions = mp.tasks.BaseOptions
ObjectDetectorOptions = mp.tasks.vision.ObjectDetectorOptions


def parse_args() -> Namespace:
    parser = ArgumentParser(prog="Sentinel")
    parser.add_argument(
        "model_path",
        metavar="model-path",
        help="Model in Tensorflow Lite format to use for object detection",
    )
    return parser.parse_args()


async def run(args) -> None:
    plugins = discover_plugins()
    print(plugins)

    # Capture video from the camera using OpenCV.
    capture = cv2.VideoCapture(0)
    if not capture.isOpened():
        print("Failed to open camera. Aborting...")
        capture.release()
        return

    async with OpenCVRawVideoStream(capture) as raw_stream, MediaPipeRawDetector(
        ObjectDetectorOptions(
            base_options=BaseOptions(model_asset_path=args.model_path),
            score_threshold=0.5,
            max_results=5,
        ),
    ) as raw_detector:
        stream = VideoStream("WebCam", raw_stream)
        detector = Detector(raw_detector)
        visualiser = DetectionResultVisualiser()
        viewer = OpenCVViewer("WebCam")

        vid_detect_emitter = VideoDetectorAlertEmitter(stream, detector)
        cooldown_filter = Cooldown(5)
        desktop_notif_sub = DesktopNotificationSubscriber()

        await stream.subscribe_async(detector)
        await detector.subscribe_async(visualiser)
        await detector.subscribe_async(vid_detect_emitter)
        await visualiser.subscribe_async(viewer)

        alert_manager = Manager()
        await alert_manager.subscribe(cooldown_filter, vid_detect_emitter)
        await alert_manager.subscribe(desktop_notif_sub, cooldown_filter)

        asyncio.create_task(stream.start())
        asyncio.create_task(alert_manager.start())

        # Quit if `q` is pressed.
        while True:
            await asyncio.sleep(0)
            if cv2.waitKey(1) == ord("q"):
                await stream.stop()
                break


def entry():
    args = parse_args()
    asyncio.run(run(args))
