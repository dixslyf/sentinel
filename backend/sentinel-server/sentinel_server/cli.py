import asyncio
import os
from argparse import ArgumentParser, Namespace

from platformdirs import PlatformDirs
from platformdirs.api import PlatformDirsABC

import sentinel_server.config
from sentinel_server.plugins import load_plugins


def parse_args(platform_dirs: PlatformDirsABC) -> Namespace:
    parser = ArgumentParser(prog="Sentinel")

    parser.add_argument(
        "--config-path",
        help="Path to the configuration file",
        default=os.path.join(platform_dirs.user_config_dir, "config.toml"),
    )

    return parser.parse_args()


async def run(args) -> None:
    config_path = (
        os.environ["SENTINEL_CONFIG_PATH"]
        if "SENTINEL_CONFIG_PATH" in os.environ
        else args.config_path
    )

    config = sentinel_server.config.get_config(config_path)

    # Load plugins.
    plugins = load_plugins(config.plugin_whitelist)


def entry() -> None:
    platform_dirs: PlatformDirsABC = PlatformDirs("sentinel")
    args = parse_args(platform_dirs)
    asyncio.run(run(args))
