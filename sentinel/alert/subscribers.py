from notifypy import Notify

from sentinel.alert import Alert, RawSubscriber


class DesktopNotificationSubscriber(RawSubscriber):
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
