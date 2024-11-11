import asyncio
from datetime import datetime

import pytest
from aioreactive import AsyncAnonymousObserver
from sentinel_core.alert import Alert, AsyncSubscriber, Emitter

from sentinel_server.alert import ReactiveEmitter, ReactiveSubscriber


@pytest.fixture
def sample_alert():
    return Alert(
        header="Test Alert",
        description="This is a test alert",
        source="Test Source",
        source_type="Test Source Type",
        timestamp=datetime.now(),
        data={"key": "value"},
    )


@pytest.mark.asyncio
async def test_reactive_subscriber_notify(mocker, sample_alert):
    async_subscriber_mock = mocker.AsyncMock(spec=AsyncSubscriber)
    reactive_subscriber = ReactiveSubscriber(async_subscriber_mock)

    await reactive_subscriber.asend(sample_alert)
    async_subscriber_mock.notify.assert_called_once_with(sample_alert)


@pytest.mark.asyncio
async def test_reactive_subscriber_notify_exception(mocker, sample_alert):
    async_subscriber_mock = mocker.AsyncMock(spec=AsyncSubscriber)
    async_subscriber_mock.notify.side_effect = Exception("Test Exception")
    reactive_subscriber = ReactiveSubscriber(async_subscriber_mock)

    await reactive_subscriber.asend(sample_alert)
    async_subscriber_mock.notify.assert_called_once_with(sample_alert)


@pytest.mark.asyncio
async def test_reactive_subscriber_athrow(mocker):
    async_subscriber_mock = mocker.AsyncMock(spec=AsyncSubscriber)
    reactive_subscriber = ReactiveSubscriber(async_subscriber_mock)
    test_exception = Exception("Test Exception")

    await reactive_subscriber.athrow(test_exception)
    async_subscriber_mock.notify.assert_called_once()
    alert = async_subscriber_mock.notify.call_args[0][0]
    assert alert.header == "Sentinel Error"
    assert "Test Exception" in alert.description


@pytest.mark.asyncio
async def test_reactive_subscriber_aclose(mocker):
    async_subscriber_mock = mocker.AsyncMock(spec=AsyncSubscriber)
    reactive_subscriber = ReactiveSubscriber(async_subscriber_mock)

    await reactive_subscriber.aclose()
    async_subscriber_mock.clean_up.assert_called_once()
