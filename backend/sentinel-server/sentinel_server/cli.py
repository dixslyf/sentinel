import logging
import os
import sys
from argparse import ArgumentParser, Namespace

import platformdirs
import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from tortoise import Tortoise

import sentinel_server.auth
import sentinel_server.config
from sentinel_server.plugins import discover_plugins, load_plugins

args: Namespace
app = FastAPI()


def parse_args() -> Namespace:
    parser = ArgumentParser(prog="Sentinel")

    parser.add_argument(
        "--config-path",
        help="Path to the configuration file",
        default=os.path.join(platformdirs.user_config_dir("sentinel"), "config.toml"),
    )

    parser.add_argument(
        "--log-level",
        "-l",
        default="info",
        choices=["debug", "info", "warning", "error", "critical"],
        help="Set the logging level",
    )

    return parser.parse_args()


@app.on_event("startup")
async def startup_event():
    # Create configuration and data directories.
    os.makedirs(platformdirs.user_config_dir("sentinel"), exist_ok=True)
    os.makedirs(platformdirs.user_data_dir("sentinel"), exist_ok=True)

    # Load configuration from the configuration file.
    config_path = os.environ.get("SENTINEL_CONFIG_PATH", args.config_path)
    config = sentinel_server.config.get_config(config_path)

    # Initialise database.
    await Tortoise.init(
        db_url=config.db_url, modules={"models": ["sentinel_server.auth"]}
    )
    await Tortoise.generate_schemas(safe=True)

    # Create the default user if it does not exist.
    await sentinel_server.auth.ensure_default_user()

    # Discover and load plugins.
    plugins = load_plugins(discover_plugins(), config.plugin_whitelist)

    logging.info("Sentinel started")


@app.on_event("shutdown")
async def shutdown_event():
    await Tortoise.close_connections()
    logging.info("Sentinel shutdown")


@app.get("/")
async def api_root():
    return JSONResponse(content={"message": "Hello world!"})


def entry() -> None:
    global args
    args = parse_args()

    # Configure logging.
    logging.basicConfig(
        stream=sys.stdout,
        level=getattr(logging, args.log_level.upper()),
        format="[%(levelname)s][%(asctime)s] %(message)s",
    )

    uvicorn.run(app, host="127.0.0.1", port=8000)
