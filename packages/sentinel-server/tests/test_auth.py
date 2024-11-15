import bcrypt
import pytest
import tortoise.contrib.test
from tortoise import Tortoise

from sentinel_server.auth import (
    create_user,
    ensure_one_user,
    hash_password,
    update_password,
    update_username,
    verify_password,
)
from sentinel_server.models import User


# Adapted from workarounds in: https://github.com/tortoise/tortoise-orm/issues/1110
@pytest.fixture
def initialise_db(request, event_loop):
    config = tortoise.contrib.test.getDBConfig(
        app_label="models", modules=["sentinel_server.models"]
    )
    event_loop.run_until_complete(tortoise.contrib.test._init_db(config))
    yield
    event_loop.run_until_complete(Tortoise._drop_databases())


@pytest.mark.asyncio
async def test_create_user(initialise_db):
    username = "testuser"
    password = "testpassword"
    user = await create_user(username, password)
    assert user.username == username
    assert bcrypt.checkpw(
        password.encode("utf-8"), user.hashed_password.encode("utf-8")
    )


@pytest.mark.asyncio
async def test_ensure_one_user(initialise_db):
    await ensure_one_user()
    assert await User.exists()


@pytest.mark.asyncio
async def test_update_username(initialise_db):
    user = await create_user("oldusername", "password")
    new_username = "newusername"
    await update_username(user.id, new_username)
    updated_user = await User.get(id=user.id)
    assert updated_user.username == new_username


@pytest.mark.asyncio
async def test_update_password(initialise_db):
    user = await create_user("username", "oldpassword")
    new_password = "newpassword"
    await update_password(user.id, new_password)
    updated_user = await User.get(id=user.id)
    assert bcrypt.checkpw(
        new_password.encode("utf-8"), updated_user.hashed_password.encode("utf-8")
    )


def test_verify_password():
    password = "password"
    hashed_password = hash_password(password)
    assert verify_password(password, hashed_password)
    assert not verify_password("wrongpassword", hashed_password)


def test_hash_password():
    password = "password"
    hashed_password = hash_password(password)
    assert bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))
