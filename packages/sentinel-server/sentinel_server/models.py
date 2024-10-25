from tortoise import fields
from tortoise.models import Model


class User(Model):
    """
    Represents a user with an ID, username and hashed password.
    """

    id = fields.IntField(pk=True)
    username = fields.CharField(max_length=255, unique=True)
    hashed_password = fields.CharField(max_length=255)


class VideoSource(Model):
    """
    Represents a video source with an associated video stream and detector.
    """

    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=255, unique=True)
    enabled = fields.BooleanField()
    plugin_name = fields.CharField(max_length=255)
    component_name = fields.CharField(max_length=255)
    config = fields.JSONField()
