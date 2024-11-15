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

    def serialise(self, path: str) -> None:
        logger.info(f'Saving configuration to: "{path}"')

        # Convert the dataclass to a dictionary and write it as TOML.
        with open(path, "w") as file:
            toml.dump(self.__dict__, file)

        logger.info(f'Saved configuration to: "{path}"')

    @classmethod
    def deserialise(cls, path: str) -> Self:
        logger.info(f'Loading configuration from: "{path}"')

        with open(path, "r") as file:
            config_data = toml.load(file)

        # TOML doesn't have sets, so we need to manually convert the whitelist into a set.
        config_data["plugin_whitelist"] = set(config_data["plugin_whitelist"])

        logger.info(f"Successfully loaded configuration from: `{path}`")

        return cls(**config_data)


def get_config(path: str) -> Configuration:
    if os.path.isfile(path):
        config = Configuration.deserialise(path)
    else:
        logger.info("No configuration file found — creating default configuration")
        config = Configuration()
        config.serialise(path)

    logger.debug(f"Configuration: {config}")
    return config
