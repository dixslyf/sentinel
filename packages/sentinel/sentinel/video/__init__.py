import cv2
from aioreactive import AsyncObservable, AsyncObserver, AsyncSubject
from sentinel_core.video import Frame, VideoStream, VideoStreamNoDataException


class ReactiveVideoStream(AsyncObservable[Frame]):
    def __init__(self, name: str, raw_stream: VideoStream):
        self._name: str = name
        self._raw_stream: VideoStream = raw_stream
        self._run: bool = False
        self._subject: AsyncSubject[Frame] = AsyncSubject()

    @property
    def name(self) -> str:
        return self._name

    @property
    def stream(self):
        return self._raw_stream

    async def subscribe_async(self, observer):
        return await self._subject.subscribe_async(observer)

    async def start(self):
        self._run = True
        while self._run:
            frame = await self._raw_stream.next_frame()
            if frame is None:
                exc = VideoStreamNoDataException(
                    "No data in the underlying video stream"
                )
                await self._subject.athrow(exc)
            await self._subject.asend(frame)

    def pause(self):
        self._run = False

    async def stop(self):
        self._run = False
        await self._subject.aclose()


class OpenCVViewer(AsyncObserver[Frame]):
    def __init__(self, win_name: str, always_show: bool = False):
        self._win_name = win_name
        self._always_show = always_show

    async def asend(self, frame: Frame):
        cv2.imshow(self._win_name, frame.data)

    async def athrow(self, error):
        if not self._always_show:
            cv2.destroyWindow(self._win_name)

    async def aclose(self):
        if not self._always_show:
            cv2.destroyWindow(self._win_name)
