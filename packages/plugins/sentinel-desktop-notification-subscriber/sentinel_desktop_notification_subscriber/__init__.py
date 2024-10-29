from collections.abc import Iterable

from notifypy import Notify
from sentinel_core.alert import Alert, Subscriber
from sentinel_core.plugins import Plugin
from sentinel_core.video import VideoStream
from sentinel_core.video.detect import Detector


class DesktopNotificationSubscriber(Subscriber):
    """
    A subscriber that receives alerts in the form of desktop notifications.
    """

    def __init__(self):
        pass

    async def notify(self, alert: Alert):
        notif = Notify()
        notif.title = alert.header
        notif.message = alert.description
        notif.send(block=False)


class DesktopNotificationSubscriberPlugin(Plugin):
    name = "Desktop Notification Subscriber"
    video_stream_classes: Iterable[type[VideoStream]] = set()
    detector_classes: Iterable[type[Detector]] = set()
    subscriber_classes: Iterable[type[Subscriber]] = {DesktopNotificationSubscriber}
