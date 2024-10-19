import dataclasses
import logging
import os
from typing import Self

import platformdirs
import toml

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class Configuration:
    db_url: str = f"sqlite://{platformdirs.user_data_dir("sentinel")}/db.sqlite3"
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
        logger.info(f"Loading configuration from: `{path}`")

        config = Configuration.deserialise(path)
        logger.info(f"Successfully loaded configuration from: `{path}`")
        logger.debug(f"Loaded configuration: {config}")

        return config
    else:
        logger.info(f"Creating default configuration at: `{path}`")
        config = Configuration()
        config.serialise(path)
        logger.info(f"Successfully wrote default configuration to: `{path}`")
        return config
