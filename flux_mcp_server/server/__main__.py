#!/usr/bin/env python3

import argparse
import os
import warnings
from contextlib import asynccontextmanager

import uvicorn

from flux_mcp_server.logger import logger

# Filter specific deprecation warnings from websockets/uvicorn
warnings.filterwarnings(
    "ignore",
    category=DeprecationWarning,
    message="websockets.server.WebSocketServerProtocol is deprecated",
)
warnings.filterwarnings("ignore", category=DeprecationWarning, module="websockets.legacy")

from fastapi import FastAPI
from mcpserver.app import init_mcp
from mcpserver.cli.args import populate_start_args
from mcpserver.cli.manager import get_manager
from mcpserver.core.config import MCPConfig
from mcpserver.routes import *

from flux_mcp_server.db import get_db
from flux_mcp_server.events.engine import EventsEngine
from flux_mcp_server.events.receiver import LocalReceiver


def get_parser():
    parser = argparse.ArgumentParser(description="Flux MCP Server")

    # Server start arguments (add port, host, config, function additions, etc.)
    populate_start_args(parser)

    # Database
    parser.add_argument(
        "--db-type",
        default=os.environ.get("FLUX_MCP_DATABASE") or "sqlite",
        choices=["sqlite", "postgres"],
        help="Database backend",
    )
    parser.add_argument("--db-path", default="server_state.db", help="Path for SQLite database")

    # Events / Receivers
    parser.add_argument(
        "--no-listener", action="store_true", help="Disable the background event listener"
    )
    parser.add_argument("--flux-uri", default=None, help="FLUX_URI for the local event listener")
    return parser


# TODO (vsoch) do we want to add other hooks?
_HOOKS = {"instance": None}


async def server_startup(args, db):
    """
    Shared startup logic.
    """
    print("   🚀 Server starting up...")

    # 1. Initialize Database
    print(f"   💾 Initializing {args.db_type} database...")
    await db.initialize()

    # 2. Start Event Engine
    if not args.no_listener:
        print(f"   🎧 Starting EventsEngine (URI: {args.flux_uri or 'local'})...")
        sink = LocalReceiver("local", db)
        engine = EventsEngine(args.flux_uri, sink)

        await engine.start()
        _HOOKS["engine"] = engine
    else:
        print("   ⚠️  Background event receiver is disabled.")


async def server_shutdown(db):
    """
    Shared shutdown logic.
    """
    # TODO: vsoch: this doesn't exit cleanly
    # because event consumer is blocking
    print("🛑 Server shutting down...")
    if _HOOKS["engine"]:
        print("   Stopping EventsEngine...")
        await _HOOKS["engine"].stop()

    await db.close()


def main():
    parser = get_parser()
    args, _ = parser.parse_known_args()

    # We detect this in sqlalchemy (get_db below) so it can be set externally.
    # We can export other envars too.
    os.environ["FLUX_MCP_DATABASE"] = args.db_type
    if args.db_type == "sqlite":
        os.environ["FLUX_MCP_DATABASE"] = args.db_path

    # Get the database instance, which can be any supported in sqlalchemy.
    # TODO try subbing in here my mcp-server library
    try:
        db = get_db()
    except Exception as e:
        logger.exit(f"🌐 Database configuration error: {e}")

    if args.config is not None:
        print(f"📖 Loading config from {args.config}")
        cfg = MCPConfig.from_yaml(args.config)
    else:
        cfg = MCPConfig.from_args(args)

    # Initialize MCP server and register Flux functions
    mcp = init_mcp(cfg.exclude, cfg.include, args.mask_error_details)
    get_manager(mcp, cfg)

    # Force running with sse / http for now
    # Note from vsoch: we should not be using sse (will be deprecated)
    if cfg.server.transport not in ["sse", "http"]:
        raise ValueError("Currently supported transports: sse/http")

    mcp_app = mcp.http_app(path=cfg.server.path)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await server_startup(args, db)

        # We use the router's context helper to activate the MCP app's internal logic
        async with mcp_app.router.lifespan_context(app):
            yield
        await server_shutdown(db)

    # create ASGI app and mount to /mcp (or other destination)
    app = FastAPI(title="Flux MCP", lifespan=lifespan)
    app.mount("/", mcp_app)

    print(f"🌍 Flux MCP Server listening on http://{cfg.server.host}:{cfg.server.port}")
    try:
        uvicorn.run(
            app,
            host=cfg.server.host,
            port=cfg.server.port,
            ssl_keyfile=cfg.server.ssl_keyfile,
            ssl_certfile=cfg.server.ssl_certfile,
            timeout_graceful_shutdown=75,
            timeout_keep_alive=60,
        )
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")


if __name__ == "__main__":
    main()
