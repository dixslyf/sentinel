import logging

import bcrypt

from sentinel_server.models import User

logger = logging.getLogger(__name__)

DEFAULT_USERNAME: str = "admin"
DEFAULT_PASSWORD: str = "password"


def verify_password(password: str, hashed_password_actual: str) -> bool:
    """
    Verifies that the given password matches the user's password.

    Args:
        password (str): The password to verify
        hashed_password_actual (str): The actual password, hashed.

    Returns:
        bool: True if the password matches; otherwise, False
    """
    return bcrypt.checkpw(
        password.encode("utf-8"), hashed_password_actual.encode("utf-8")
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


async def ensure_one_user() -> None:
    """
    Ensures that at least one user exists in the database.
    If there are no users, a default user is created and saved into the database.

    The default username is `DEFAULT_USERNAME` while the default password
    is `DEFAULT_PASSWORD`.
    """
    logging.info("Checking if there is at least one user")

    if await User.exists():
        logging.info("At least one user already exists")
        return

    logging.info("Creating default user as there are no users")
    await create_user(DEFAULT_USERNAME, DEFAULT_PASSWORD)
    logging.info("Created default user")


async def update_username(id: int, new_username: str) -> None:
    """
    Updates the username for the given user ID.
    """
    user = await User.get(id=id)
    user.username = new_username
    await user.save()
    logger.info(f'Updated username for user id `{id}` to "{new_username}"')


async def update_password(id: int, password: str) -> None:
    """
    Updates the password for the given user ID.
    """
    user = await User.get(id=id)
    user.hashed_password = hash_password(password)
    await user.save()
    logger.info(f"Updated password for user id `{id}`")
