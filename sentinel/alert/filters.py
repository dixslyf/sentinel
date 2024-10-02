import time

from aioreactive import AsyncSubject

from sentinel.alert import Alert, Emitter, Subscriber


class Cooldown(Emitter, Subscriber):
    def __init__(self, duration: float):
        self._time_start: float = 0
        self._duration: float = duration
        self._subject_out: AsyncSubject = AsyncSubject()

    async def subscribe_async(self, observer):
        await self._subject_out.subscribe_async(observer)

    async def asend(self, alert: Alert):
        cur_time = time.time()
        if cur_time >= self._time_start + self._duration:
            self._time_start = cur_time
            await self._subject_out.asend(alert)

    async def athrow(self, error: Exception):
        await self._subject_out.athrow(error)

    async def aclose(self):
        await self._subject_out.aclose()
