from argparse import ArgumentParser

import cv2
import mediapipe as mp
import numpy as np

from sentinel.detect import MediaPipeAsyncDetector, visualise_detections
from sentinel.video import Frame, OpenCVVideoSource

# MediaPipe has a weird way of importing stuff.
BaseOptions = mp.tasks.BaseOptions
ObjectDetectorOptions = mp.tasks.vision.ObjectDetectorOptions


def parse_args():
    parser = ArgumentParser(prog="Sentinel")
    parser.add_argument(
        "model_path",
        metavar="model-path",
        help="Model in Tensorflow Lite format to use for object detection",
    )
    return parser.parse_args()


def run():
    args = parse_args()

    # Capture video from the camera using OpenCV.
    capture = cv2.VideoCapture(0)
    if not capture.isOpened():
        print("Failed to open camera. Aborting...")
        capture.release()
        return

    # Create the video source and object detector.
    with OpenCVVideoSource(capture) as source, MediaPipeAsyncDetector(
        ObjectDetectorOptions(
            base_options=BaseOptions(model_asset_path=args.model_path),
            score_threshold=0.5,
            max_results=5,
        )
    ) as detector:
        while True:
            # Capture a single frame.
            input_frame = source.next_frame()
            if input_frame is None:
                print("Failed to grab frame (disconnected?). Aborting...")
                break

            detector.detect_async(input_frame)

            # The detector updates the `result` variable asychronously.
            # We visualise the result onto the frame and then show it.
            last_result = detector.last_result()
            if last_result is not None:
                frame_r, detections = last_result

                # The MediaPipe detector uses a non-writable NumPy array as the data,
                # so we need to copy it.
                frame_w = Frame(frame_r.timestamp, np.copy(frame_r.data))

                # Display the resulting frame
                frame_v = visualise_detections(frame_w, detections)
                cv2.imshow("frame", frame_v.data)

                # Quit if `q` is pressed.
                if cv2.waitKey(1) == ord("q"):
                    break

        cv2.destroyAllWindows()
