import time
from asyncio import Queue

from sentinel_core.alert import Alert, Emitter, Subscriber


class Cooldown(Emitter, Subscriber):
    def __init__(self, duration: float):
        self._time_start: float = 0
        self._duration: float = duration
        self._queue: Queue = Queue()

    async def notify(self, alert: Alert) -> None:
        cur_time = time.time()
        if cur_time >= self._time_start + self._duration:
            self._time_start = cur_time
            await self._queue.put(alert)

    async def next_alert(self) -> Alert:
        alert = await self._queue.get()
        self._queue.task_done()
        return alert
