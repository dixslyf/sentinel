from notifypy import Notify

from sentinel.alert import Subscriber


class DesktopNotificationSubscriber(Subscriber):
    """
    A subscriber that receives alerts in the form of desktop notifications.
    """

    def __init__(self):
        pass

    async def asend(self, alert):
        notif = Notify()
        notif.title = alert.header
        notif.message = alert.description
        notif.send(block=False)

    async def athrow(self, error: Exception):
        notif = Notify()
        notif.title = "Source error"
        notif.message = str(error)
        notif.send(block=False)

    async def aclose(self):
        pass
