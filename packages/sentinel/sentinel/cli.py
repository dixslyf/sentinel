import asyncio
from argparse import ArgumentParser, Namespace

import cv2
import mediapipe as mp

from sentinel.alert import AlertManager
from sentinel.alert.filters import Cooldown
from sentinel.alert.video import VideoDetectorAlertEmitter
from sentinel.plugins import load_plugins
from sentinel.video import OpenCVViewer, ReactiveVideoStream
from sentinel.video.detect import DetectionResultVisualiser, ReactiveDetector

# MediaPipe has a weird way of importing stuff.
BaseOptions = mp.tasks.BaseOptions
ObjectDetectorOptions = mp.tasks.vision.ObjectDetectorOptions


def parse_args() -> Namespace:
    parser = ArgumentParser(prog="Sentinel")

    parser.add_argument(
        "detector_plugin",
        metavar="detector-plugin",
        help='Plugin to use for the object detector model ("ultralytics" or "mediapipe")',
        choices=["ultralytics", "mediapipe"],
    )

    parser.add_argument(
        "model_path",
        metavar="model-path",
        help="Path to the object detection model (format depends on the plugin)",
    )

    return parser.parse_args()


async def run(args) -> None:
    # Load plugins.
    plugins = load_plugins()
    print(f"Loaded plugins: {[plugin.name for plugin in plugins]}")

    opencv_plugin = next(plugin for plugin in plugins if plugin.name == "OpenCV")
    ultralytics_plugin = next(
        plugin for plugin in plugins if plugin.name == "Ultralytics"
    )
    mediapipe_plugin = next(plugin for plugin in plugins if plugin.name == "MediaPipe")
    desktop_notification_subscriber_plugin = next(
        plugin for plugin in plugins if plugin.name == "Desktop Notification Subscriber"
    )

    # Load the classes we need from the plugins.
    # For this prototype, we already know what classes we need.
    # In the final system, we will need to have a way for users to
    # select and initialise these classes.
    OpenCVVideoStream = next(
        cls
        for cls in opencv_plugin.video_stream_classes
        if cls.__name__ == "OpenCVVideoStream"
    )

    UltralyticsDetector = next(
        cls
        for cls in ultralytics_plugin.detector_classes
        if cls.__name__ == "UltralyticsDetector"
    )

    MediaPipeDetector = next(
        cls
        for cls in mediapipe_plugin.detector_classes
        if cls.__name__ == "MediaPipeDetector"
    )

    DesktopNotificationSubscriber = next(
        cls
        for cls in desktop_notification_subscriber_plugin.subscriber_classes
        if cls.__name__ == "DesktopNotificationSubscriber"
    )

    # Capture video from the camera using OpenCV.
    capture = cv2.VideoCapture(0)
    if not capture.isOpened():
        print("Failed to open camera. Aborting...")
        capture.release()
        return

    async def start(detector) -> None:
        async with OpenCVVideoStream(capture) as stream:  # type: ignore[call-arg, attr-defined]
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

    if args.detector_plugin == "mediapipe":
        async with MediaPipeDetector(
            ObjectDetectorOptions(
                base_options=BaseOptions(model_asset_path=args.model_path),
                score_threshold=0.5,
                max_results=5,
            ),
        ) as detector:  # type: ignore[call-arg, attr-defined]
            await start(detector)
    elif args.detector_plugin == "ultralytics":
        detector = UltralyticsDetector("YOLO", "yolo_fine_tuned.pt")  # type: ignore[call-arg]
        await start(detector)
    else:
        raise AssertionError("Unreachable")


def entry():
    args = parse_args()
    asyncio.run(run(args))
