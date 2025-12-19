import argparse
import asyncio
import logging
import os

from flux_mcp_server.db.sqlite import JobDatabase

from .events.engine import EventsEngine
from .events.sinks import LocalDbSink, RemoteApiSink


def setup_logging():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


async def run_local(args):
    """
    Mode 1: Run alongside the server (or with shared volume).
    """
    db_path = os.path.abspath(args.db_path)
    logging.info(f"Starting Local EventsEngine. Cluster: {args.cluster}, DB: {db_path}")

    db = JobDatabase(db_path)
    sink = LocalDbSink(args.cluster, db)
    engine = EventsEngine(args.uri, sink)

    await engine.start()

    # Block forever (the engine runs in a background thread)
    stop_event = asyncio.Event()
    await stop_event.wait()


async def run_remote(args):
    """
    Mode 2: Run on a remote cluster, forwarding events to the MCP server.
    """
    logging.info(f"Starting Remote EventsEngine. Target: {args.server_url}")

    sink = RemoteApiSink(args.cluster, args.server_url)
    engine = EventsEngine(args.uri, sink)

    await engine.start()

    stop_event = asyncio.Event()
    await stop_event.wait()


def main():
    parser = argparse.ArgumentParser(description="Flux MCP Events Service")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Command: events-local
    p_local = subparsers.add_parser("events-local", help="Write directly to DB")
    p_local.add_argument("--cluster", required=True, help="Name of this cluster")
    p_local.add_argument("--db-path", default="server.db", help="Path to SQLite DB")
    p_local.add_argument("--uri", default=None, help="Optional FLUX_URI")

    # Command: events-remote
    p_remote = subparsers.add_parser("events-remote", help="Forward to MCP Server")
    p_remote.add_argument("--cluster", required=True)
    p_remote.add_argument("--server-url", required=True, help="http://host:port/sse")
    p_remote.add_argument("--uri", default=None)

    args = parser.parse_args()
    setup_logging()

    try:
        if args.command == "events-local":
            asyncio.run(run_local(args))
        elif args.command == "events-remote":
            asyncio.run(run_remote(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
