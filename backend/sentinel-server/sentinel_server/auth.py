import logging

import bcrypt
import tortoise
from tortoise import fields
from tortoise.models import Model

DEFAULT_USERNAME: str = "root"
DEFAULT_PASSWORD: str = "password"


class User(Model):
    id = fields.IntField(pk=True)
    username = fields.CharField(max_length=255, unique=True)
    hashed_password = fields.CharField(max_length=255)

    def verify_password(self, password: str) -> bool:
        return bcrypt.checkpw(
            password.encode("utf-8"), self.hashed_password.encode("utf-8")
        )


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


async def create_user(username: str, password: str) -> User:
    user = await User(username=username, hashed_password=hash_password(password))
    await user.save()
    return user


async def ensure_default_user() -> User:
    logging.info("Checking if default user exists")
    try:
        # Check if a user with the default username already exists.
        user = await User.get(username=DEFAULT_USERNAME)
        logging.info("Default user already exists")
    except tortoise.exceptions.DoesNotExist:
        logging.info("Creating default user as it does not exist")
        user = await create_user(DEFAULT_USERNAME, DEFAULT_PASSWORD)
        logging.info("Created default user")
    return user
