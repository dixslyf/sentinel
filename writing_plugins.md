# Writing Plugins

## Components

Sentinel is extendable through plugins.
A plugin provides a set of _components_,
each of which can be one of the following types:

- _Video stream_: Provides a stream of video frames.

- _Detector_: Detects objects from video frames.

- _Subscriber_: Receives alerts about detected objects.

Each of these types can be further divided into _asynchronous_ and _synchronous_ variants.
For a better understanding of asynchronous programming in Python,
please see [`asyncio`](https://docs.python.org/3/library/asyncio.html).
You should prefer writing asynchronous components as
you can have more control over when execution is "paused".
However, when working with non-asynchronous libraries,
it is not convenient to write an asynchronous component
— in such cases, you may want to write a synchronous component instead.
Internally, Sentinel will wrap the synchronous component with
an asynchronous wrapper (Sentinel is heavily based on asynchronous programming).

## Plugin Basics

### Entry Point

To write a plugin, you must have `sentinel-core` as a dependency.
Your plugin must expose a `Plugin` instance (provided by `sentinel-core`)
through the [entry points specification](https://packaging.python.org/en/latest/specifications/entry-points/),
under the `sentinel.plugins` group.
How to do this depends on what packaging tool you are using.
As an example, if you use [Poetry](https://python-poetry.org/) to package your plugin,
then include something similar to the following in `pyproject.toml`:

```toml
[tool.poetry.plugins."sentinel.plugins"]
sentinel-example-plugin = "sentinel_example_plugin:plugin"
```

In the above, `sentinel_example_plugin` is the name of the module
providing a `Plugin` instance called `plugin`.
For other packaging tools, please refer to their respective documentation.

### Creating a Plugin and its Components

A `Plugin` is constructed by passing a `frozenset` of `ComponentDescriptor`s
to its constructor.
A `ComponentDescriptor` provides all details of a component,
including the component's implementation (by exposing the component's class),
type and a description of arguments.

`sentinel-core` provides 6 component protocols (interfaces) that you can implement.
These protocols correspond to the component types described before.
The protocols are:

- `SyncVideoStream`

- `AsyncVideoStream`

- `SyncDetector`

- `AsyncDetector`

- `SyncSubscriber`

- `AsyncSubscriber`

Explaining how to write a plugin is best demonstrated with an example:

```python
from sentinel_core.alert import Alert, SyncSubscriber
from sentinel_core.plugins import ComponentArgDescriptor, ComponentDescriptor, ComponentKind, Plugin


class SimpleSubscriber(SyncSubscriber):
    """
    A subscriber that prints received alerts.
    """

    def __init__(self, prefix: str = "") -> None:
        self._prefix = prefix

    def notify(self, alert: Alert) -> None:
        print(f"{self._prefix}{alert}")

    def clean_up(self) -> None:
        pass


_component_descriptor = ComponentDescriptor(
    display_name="Simple Subscriber",
    kind=ComponentKind.SyncSubscriber,
    cls=SimpleSubscriber,
    args=(
        ComponentArgDescriptor(
            display_name="Prefix",
            arg_name="prefix",
            option_type=str,
            required=True,
            default="",
        ),
    ),
)


plugin = Plugin(frozenset({_component_descriptor}))
```

In the example above, we've written a simple synchronous subscriber plugin
that prints received alerts with an optional prefix.
As the subscriber is synchronous, the `SimpleSubscriber` class
subclasses the `SyncSubscriber` protocol,
which requires the `notify()` and `clean_up()` methods to be implemented
The `clean_up()` method is called when the component is disabled or removed (using the user interface).
All component protocols support the `clean_up()` method (however, for asynchronous components,
remember to add `async` to it).
Additionally, the `SimpleSubscriber`'s `__init__()` method accepts a prefix as a string.

With the component class written,
we now need to create a `ComponentDescriptor` for it.
A `ComponentDescriptor` accepts the following arguments:

- `display_name: str`: A display name for the component.

- `kind: ComponentKind`: The component's type, one of:

  - `ComponentKind.AsyncVideoStream`

  - `ComponentKind.SyncVideoStream`

  - `ComponentKind.AsyncDetector`

  - `ComponentKind.SyncDetector`

  - `ComponentKind.AsyncSubscriber`

  - `ComponentKind.SyncSubscriber`

  In the example above, this would be `ComponentKind.SyncDetector`.

- `cls: type[T]`: The component class. In the example above, this would be the `SimpleSubscriber` class.

- `args: tuple[ComponentArgDescriptor, ...]`: A tuple of `ComponentArgDescriptor`s,
  each of which describes a single argument to the component's constructor.
  In the example above, we have a single `prefix` argument.

- `args_transform: Optional[Callable[[dict[str, Any]], dict[str, Any]]] = None`: An optional function
  to transform the arguments before passing them to the component's constructor.
  This can be useful to convert the arguments to different types
  as Sentinel's user interface will pass arguments as strings.

Finally, with the `ComponentDescriptor` defined,
we can construct a `Plugin`.
In the example, our plugin only has a single `ComponentDescriptor`,
so we create a `frozenset` containing this `ComponentDescriptor`
and pass it to the `Plugin` constructor.

For more information about the exact interface required by the component protocols,
please refer to their respective code and documentation.
You may also want to look at the implementation of the plugins provided by Sentinel
to get a better grasp on how to write plugins.
