import json
import logging
from argparse import ArgumentParser, Namespace
from typing import Any

import aiohttp
import aiohttp.web

logger = logging.getLogger(__name__)


async def alert_handler(request: aiohttp.web.Request) -> aiohttp.web.WebSocketResponse:
    ws = aiohttp.web.WebSocketResponse()
    await ws.prepare(request)

    logger.info("Client connected to the WebSocket server.")

    async for message in ws:
        if message.type == aiohttp.WSMsgType.TEXT:
            print(message.data)
            alert_json: dict[str, Any] = json.loads(message.data)
            logger.info(
                "Received Alert:\n"
                f"Header: {alert_json["header"]}\n"
                f"Source: {alert_json["source"]}\n"
                f"Source Type: {alert_json["source_type"]}\n"
                f"Description: {alert_json["description"]}\n"
                f"Timestamp: {alert_json["timestamp"]}\n"
                f"Data: {alert_json["data"]}\n"
            )
        elif message.type == aiohttp.WSMsgType.ERROR:
            logger.error(f"Connection closed with exception: {ws.exception()}")

    logger.info("Connection closed")

    return ws


def parse_args() -> Namespace:
    parser = ArgumentParser()

    parser.add_argument(
        "-a",
        "--host",
        type=str,
        help="The host address",
        default="localhost",
    )

    parser.add_argument(
        "-p",
        "--port",
        type=int,
        help="The port to serve on",
        default=8001,
    )

    return parser.parse_args()


def entry() -> None:
    args: Namespace = parse_args()

    app: aiohttp.web.Application = aiohttp.web.Application()
    app.router.add_get("/", alert_handler)

    aiohttp.web.run_app(app, host=args.host, port=args.port)
