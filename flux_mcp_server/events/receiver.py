import json
import logging
from fastmcp import Client
from flux_mcp_server.db.interface import DatabaseBackend

logger = logging.getLogger(__name__)

class EventReceiver:
    async def send(self, event: dict):
        raise NotImplementedError

class LocalReceiver(EventReceiver):
    """
    Writes directly to the internal database backend.
    """
    def __init__(self, cluster_name: str, db: DatabaseBackend):
        self.cluster = cluster_name
        self.db = db

    async def send(self, event: dict):
        # CRITICAL: This must be awaited!
        # If you miss 'await', the data is lost silently.
        try:
            await self.db.record_event(self.cluster, event)
        except Exception as e:
            logger.error(f"Failed to write event to DB: {e}")

class RemoteReceiver(EventReceiver):
    """
    Forwards events to the MCP Server via tool call.
    """
    def __init__(self, cluster_name: str, server_url: str):
        self.cluster = cluster_name
        self.client = Client(server_url, name="FluxScribe")
        self._connected = False

    async def _ensure_connect(self):
        if not self._connected:
            await self.client.connect()
            self._connected = True

    async def send(self, event: dict):
        await self._ensure_connect()
        await self.client.call_tool(
            "ingest_flux_event",
            {
                "cluster_name": self.cluster,
                "event_json": json.dumps(event)
            }
        )