import dataclasses
from enum import Enum
from typing import Any, Callable, Optional, Self

from sentinel_core.alert import Subscriber
from sentinel_core.video import AsyncVideoStream, SyncVideoStream
from sentinel_core.video.detect import AsyncDetector, SyncDetector


@dataclasses.dataclass(frozen=True)
class Choice:
    display_name: str
    value: Any

    @classmethod
    def from_string(cls, value: str) -> Self:
        return cls(display_name=value, value=value)


@dataclasses.dataclass(frozen=True)
class ComponentArgDescriptor[T]:
    display_name: str
    arg_name: str
    option_type: T
    required: bool
    default: Optional[T] = None
    choices: Optional[frozenset[Choice]] = None
    validator: Optional[Callable[[T], Optional[str]]] = None


class ComponentKind(Enum):
    AsyncVideoStream = 0
    SyncVideoStream = 1
    AsyncDetector = 2
    SyncDetector = 3
    Subscriber = 4


@dataclasses.dataclass(frozen=True)
class ComponentDescriptor[
    T: AsyncVideoStream | SyncVideoStream | AsyncDetector | SyncDetector | Subscriber
]:
    display_name: str
    kind: ComponentKind
    cls: type[T]
    args: tuple[ComponentArgDescriptor, ...]
    args_transform: Optional[Callable[[dict[str, Any]], dict[str, Any]]] = None


@dataclasses.dataclass(frozen=True)
class Plugin:
    components: frozenset[ComponentDescriptor]

    def find_component(
        self, predicate: Callable[[ComponentDescriptor], bool]
    ) -> Optional[ComponentDescriptor]:
        return next(
            (comp for comp in self.components if predicate(comp)),
            None,
        )
