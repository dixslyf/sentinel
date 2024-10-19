import asyncio
import logging
import os
import sys
from argparse import ArgumentParser, Namespace

from platformdirs import PlatformDirs
from platformdirs.api import PlatformDirsABC

import sentinel_server.config
from sentinel_server.plugins import discover_plugins, load_plugins


def parse_args(platform_dirs: PlatformDirsABC) -> Namespace:
    parser = ArgumentParser(prog="Sentinel")

    parser.add_argument(
        "--config-path",
        help="Path to the configuration file",
        default=os.path.join(platform_dirs.user_config_dir, "config.toml"),
    )

    parser.add_argument(
        "--log-level",
        "-l",
        default="info",
        choices=["debug", "info", "warning", "error", "critical"],
        help="Set the logging level",
    )

    return parser.parse_args()


async def run(args) -> None:
    # Configure logging.
    logging.basicConfig(
        stream=sys.stdout,
        level=getattr(logging, args.log_level.upper()),
        format="[%(levelname)s][%(asctime)s] %(message)s",
    )

    # Load configuration from the configuration file.
    config_path = (
        os.environ["SENTINEL_CONFIG_PATH"]
        if "SENTINEL_CONFIG_PATH" in os.environ
        else args.config_path
    )
    config = sentinel_server.config.get_config(config_path)

    # Discover and load plugins.
    plugins = load_plugins(discover_plugins(), config.plugin_whitelist)


def entry() -> None:
    # For getting common directories platform-agnostically (e.g., config directory).
    platform_dirs: PlatformDirsABC = PlatformDirs("sentinel")

    args = parse_args(platform_dirs)
    asyncio.run(run(args))
