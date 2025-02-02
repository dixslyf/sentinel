from tortoise import fields
from tortoise.models import Model


class User(Model):
    """
    Represents a user with an ID, username and hashed password.
    """

    id = fields.IntField(primary_key=True)
    username = fields.CharField(max_length=255, unique=True)
    hashed_password = fields.CharField(max_length=255)


class VideoSource(Model):
    """
    Represents a video source with an associated video stream and detector.
    """

    id = fields.IntField(primary_key=True)
    name = fields.CharField(max_length=255, unique=True)
    enabled = fields.BooleanField()

    detect_interval = fields.FloatField()

    vidstream_plugin_name = fields.CharField(max_length=255)
    vidstream_component_name = fields.CharField(max_length=255)
    vidstream_config = fields.JSONField()

    detector_plugin_name = fields.CharField(max_length=255)
    detector_component_name = fields.CharField(max_length=255)
    detector_config = fields.JSONField()


class Subscriber(Model):
    """
    Represents a subscriber that subscribes to alerts.
    """

    id = fields.IntField(primary_key=True)
    name = fields.CharField(max_length=255, unique=True)
    enabled = fields.BooleanField()

    plugin_name = fields.CharField(max_length=255)
    component_name = fields.CharField(max_length=255)
    config = fields.JSONField()


class Alert(Model):
    """
    Represents an alert.
    """

    id = fields.IntField(primary_key=True)
    header = fields.CharField(max_length=256)
    description = fields.CharField(max_length=2048)
    source = fields.CharField(max_length=255)
    source_type = fields.CharField(max_length=255)
    source_deleted = fields.BooleanField(default=False)
    timestamp = fields.DatetimeField(auto_now=True)
    data = fields.JSONField()
