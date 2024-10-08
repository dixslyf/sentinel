import asyncio
from argparse import ArgumentParser, Namespace

import cv2
import mediapipe as mp

from sentinel.alert import AlertManager
from sentinel.alert.filters import Cooldown
from sentinel.alert.subscribers import DesktopNotificationSubscriber
from sentinel.alert.video import VideoDetectorAlertEmitter
from sentinel.plugins import discover_plugins
from sentinel.video import OpenCVVideoStream, OpenCVViewer, ReactiveVideoStream
from sentinel.video.detect import (
    DetectionResultVisualiser,
    MediaPipeDetector,
    ReactiveDetector,
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

    async with OpenCVVideoStream(capture) as stream, MediaPipeDetector(
        ObjectDetectorOptions(
            base_options=BaseOptions(model_asset_path=args.model_path),
            score_threshold=0.5,
            max_results=5,
        ),
    ) as detector:
        r_stream = ReactiveVideoStream("WebCam", stream)
        r_detector = ReactiveDetector(detector)
        r_visualiser = DetectionResultVisualiser()
        r_viewer = OpenCVViewer("WebCam")

        vid_detect_emitter = VideoDetectorAlertEmitter(r_stream, r_detector)
        cooldown_filter = Cooldown(5)
        desktop_notif_sub = DesktopNotificationSubscriber()

        await r_stream.subscribe_async(r_detector)
        await r_detector.subscribe_async(r_visualiser)
        await r_detector.subscribe_async(vid_detect_emitter)
        await r_visualiser.subscribe_async(r_viewer)

        alert_manager = AlertManager()
        await alert_manager.subscribe(cooldown_filter, vid_detect_emitter)
        await alert_manager.subscribe(desktop_notif_sub, cooldown_filter)

        asyncio.create_task(r_stream.start())
        asyncio.create_task(alert_manager.start())

        # Quit if `q` is pressed.
        while True:
            await asyncio.sleep(0)
            if cv2.waitKey(1) == ord("q"):
                await r_stream.stop()
                break


def entry():
    args = parse_args()
    asyncio.run(run(args))
