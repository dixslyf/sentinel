import logging

import bcrypt
import tortoise
from tortoise import fields
from tortoise.models import Model

DEFAULT_USERNAME: str = "root"
DEFAULT_PASSWORD: str = "password"


class User(Model):
    """
    Represents a user with an ID, username and hashed password.
    """

    id = fields.IntField(pk=True)
    username = fields.CharField(max_length=255, unique=True)
    hashed_password = fields.CharField(max_length=255)

    def verify_password(self, password: str) -> bool:
        """
        Verifies that the given password matches the user's password.

        Args:
            password (str): The password to verify

        Returns:
            True if the password matches; otherwise, False
        """
        return bcrypt.checkpw(
            password.encode("utf-8"), self.hashed_password.encode("utf-8")
        )


def hash_password(password: str) -> str:
    """
    Hashes the given password with a random salt using bcrypt.

    Args:
        password (str): The password to hash

    Returns:
        str: The hashed password
    """
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


async def create_user(username: str, password: str) -> User:
    """
    Creates a user with the given username and password, and stores the user into the database.

    Args:
        username (str): The user's username
        password (str): The user's password

    Returns:
        User: The created user
    """
    user = await User(username=username, hashed_password=hash_password(password))
    await user.save()
    return user


async def ensure_default_user() -> User:
    """
    Ensures that the default user exists in the database.
    If the default user does not exist, it is created and saved into the database.

    The default username is `DEFAULT_USERNAME` while the default password
    is `DEFAULT_PASSWORD`.

    Returns:
        User: The existing or newly created default user
    """
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
