from abc import abstractmethod
from collections.abc import Iterable

from sentinel_core.alert import Subscriber
from sentinel_core.video import VideoStream
from sentinel_core.video.detect import Detector


class Plugin:
    def __init__(self):
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Returns the name of the plugin.
        """

    @property
    @abstractmethod
    def video_stream_classes(self) -> Iterable[type[VideoStream]]:
        """
        Returns the video source classes provided by this plugin.
        """

    @property
    @abstractmethod
    def detector_classes(self) -> Iterable[type[Detector]]:
        """
        Returns the object detector classes provided by this plugin.
        """

    @property
    @abstractmethod
    def subscriber_classes(self) -> Iterable[type[Subscriber]]:
        """
        Returns the subscriber classes provided by this plugin.
        """
