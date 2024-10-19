import dataclasses
import os
from typing import Self

import toml


@dataclasses.dataclass
class Configuration:
    db_url: str = "sqlite://db.sqlite3"
    plugin_whitelist: set[str] = dataclasses.field(default_factory=set)

    def serialise(self, path: str):
        # Convert the dataclass to a dictionary and write it as TOML.
        with open(path, "w") as file:
            toml.dump(self.__dict__, file)

    @classmethod
    def deserialise(cls, path: str) -> Self:
        with open(path, "r") as file:
            config_data = toml.load(file)
        return cls(**config_data)


def get_config(path: str) -> Configuration:
    if os.path.isfile(path):
        print(f"Loading configuration from: {path}")
        return Configuration.deserialise(path)
    else:
        print(f"Creating default configuration file at: {path}")
        config = Configuration()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        config.serialise(path)
        return config
