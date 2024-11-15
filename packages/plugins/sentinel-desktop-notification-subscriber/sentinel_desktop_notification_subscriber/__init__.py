from notifypy import Notify
from sentinel_core.alert import Alert, SyncSubscriber
from sentinel_core.plugins import ComponentDescriptor, ComponentKind, Plugin


class DesktopNotificationSubscriber(SyncSubscriber):
    """
    A subscriber that receives alerts in the form of desktop notifications.
    """

    def __init__(self) -> None:
        pass

    def notify(self, alert: Alert) -> None:
        notif = Notify()
        notif.title = f"{alert.header} (source: {alert.source})"
        notif.message = alert.description
        notif.send()


_component_descriptor = ComponentDescriptor(
    display_name="Desktop Notification Subscriber",
    kind=ComponentKind.SyncSubscriber,
    cls=DesktopNotificationSubscriber,
    args=(),
)


plugin = Plugin(frozenset({_component_descriptor}))
