import dataclasses
from abc import abstractmethod
from collections.abc import Sequence
from enum import Enum
from typing import Any, Callable, Optional, Protocol, Self

from sentinel_core.alert import Subscriber
from sentinel_core.video import VideoStream
from sentinel_core.video.detect import Detector


@dataclasses.dataclass(frozen=True)
class Choice:
    display_name: str
    value: Any

    @classmethod
    def from_string(cls, value: str) -> Self:
        return cls(display_name=value, value=value)


@dataclasses.dataclass
class ComponentArgDescriptor[T]:
    display_name: str
    arg_name: str
    option_type: T
    required: bool
    default: Optional[T] = None
    choices: Optional[set[Choice]] = None
    validator: Optional[Callable[[T], Optional[str]]] = None
    transform: Optional[Callable[[T], Any]] = None


class ComponentKind(Enum):
    VideoStream = 0
    Detector = 1
    Subscriber = 2


@dataclasses.dataclass
class ComponentDescriptor[T: VideoStream | Detector | Subscriber]:
    display_name: str
    kind: ComponentKind
    cls: type[T]
    args: Sequence[ComponentArgDescriptor]


class Plugin(Protocol):
    @property
    @abstractmethod
    def components(self) -> Sequence[ComponentDescriptor]:
        """
        Returns the components provided by this plugin.
        """
