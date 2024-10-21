import logging
import os
import sys
from typing import Annotated

import platformdirs
from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from tortoise import Tortoise

import sentinel_server.auth
import sentinel_server.config
from sentinel_server.plugins import discover_plugins, load_plugins

app = FastAPI()
security = HTTPBasic()


@app.on_event("startup")
async def startup_event():
    # Configure logging.
    log_level = os.environ.get("SENTINEL_LOG_LEVEL", "INFO").upper()
    if log_level not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
        log_level = "NOTSET"

    logging.basicConfig(
        stream=sys.stdout,
        level=getattr(logging, log_level),
        format="[%(levelname)s][%(asctime)s] %(message)s",
    )

    # Create configuration and data directories.
    os.makedirs(platformdirs.user_config_dir("sentinel"), exist_ok=True)
    os.makedirs(platformdirs.user_data_dir("sentinel"), exist_ok=True)

    # Load configuration from the configuration file.
    config_path = os.environ.get(
        "SENTINEL_CONFIG_PATH",
        os.path.join(platformdirs.user_config_dir("sentinel"), "config.toml"),
    )
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


@app.post("/login")
async def login(credentials: Annotated[HTTPBasicCredentials, Depends(security)]):
    logging.info(f"Received login credentials for: {credentials.username}")

    user: sentinel_server.auth.User = await sentinel_server.auth.User.get_or_none(
        username=credentials.username
    )

    if not user or not user.verify_password(credentials.password):
        logging.info(f"Authentication failed for: {credentials.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )

    logging.info(f"Authentication succeeded for: {credentials.username}")
    jwt_token = sentinel_server.auth.create_jwt_access_token(user.username)
    return {"access_token": jwt_token, "token_type": "bearer"}


def entry() -> None:
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
