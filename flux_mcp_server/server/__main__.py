#!/usr/bin/env python3

import argparse
import asyncio
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
from fastmcp.tools.tool import Tool

from flux_mcp_server.db import get_db
from flux_mcp_server.events.engine import EventsEngine
from flux_mcp_server.events.receiver import LocalReceiver
from flux_mcp_server.registry import TOOLS

from .app import init_mcp


def get_parser():
    parser = argparse.ArgumentParser(description="Flux MCP Server")

    # Server
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8089, help="Port to listen on")
    parser.add_argument(
        "--transport", default="http", choices=["sse", "stdio", "http"], help="MCP Transport type"
    )
    parser.add_argument(
        "--mount-to", default="/mcp", help="Mount path for server (defaults to /mcp)"
    )

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


def register_tools(server_instance):
    """
    Registers selected tools from the registry with the server.
    We want this to fail if a function does not register.
    """
    print("🔌 Registering tools...")
    for func in TOOLS:
        tool_obj = Tool.from_function(func)
        server_instance.add_tool(tool_obj)
        print(f"   ✅ Registered: {func.__name__}")


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
    try:
        db = get_db()
    except Exception as e:
        logger.exit(f"🌐 Database configuration error: {e}")

    # Initialize MCP server and register Flux functions
    mcp = init_mcp()
    register_tools(mcp)

    # Note from vsoch: we should not be using sse (will be deprecated)
    if args.transport in ["sse", "http"]:

        mcp_app = mcp.http_app(path=args.mount_to)

        @asynccontextmanager
        async def lifespan(app: FastAPI):
            # A. Custom Startup
            await server_startup(args, db)

            # B. Chain FastMCP Startup (Required for Task Groups/SSE)
            # We use the router's context helper to activate the MCP app's internal logic
            async with mcp_app.router.lifespan_context(app):
                yield

            # C. Custom Shutdown
            await server_shutdown(db)

        # Create ASGI app and mount to /mcp (or other destination)
        app = FastAPI(title="Flux MCP", lifespan=lifespan)
        app.mount("/", mcp_app)

        print(f"🌍 Flux MCP Server listening on http://{args.host}:{args.port}")
        try:
            uvicorn.run(app, host=args.host, port=args.port)
            # TODO: vsoch: this doesn't work with startup / shudown
            # mcp.run(transport=args.transport, port=args.port, host=args.host)
        except KeyboardInterrupt:
            print("\n👋 Shutting down...")

    elif args.transport == "stdio":

        async def run_stdio():
            await server_startup(args, db)
            try:
                await mcp.run_stdio()
            finally:
                await server_shutdown(db)

        try:
            asyncio.run(run_stdio())
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
