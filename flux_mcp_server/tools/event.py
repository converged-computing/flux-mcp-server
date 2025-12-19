import json

from fastmcp import Context

from ..db.sqlite import JobDatabase
from ..scribe.sources import EventSource

# This is the set of MCP functions for the event scribes. E.g., we write to our
# database interface via an MCP call. Importantly, we need to make sure this
# function is not exposed to ANY agent that might choose to call it with fake
# events.

DATABASE: JobDatabase = None


def init_ingest_tool(db: JobDatabase):
    global DATABASE
    DATABASE = db


def ingest_flux_event(cluster_name: str, event_json: str, ctx: Context = None) -> str:
    """
    SYSTEM TOOL: Ingests raw Flux events into the database.
    This should only be called by the Scribe service, not by Users/Agents.
    """
    # TODO (vsoch and others): we need some security check here.
    # Here is how to get session info.
    current_user = ctx.session.initialization_options.get("clientInfo", {}).get("name")

    # Simple check: Only allow clients identifying as "FluxScribe"
    # This is dumb and not good enough, I was just testing looking at metadata.
    if current_user != "FluxScribe":
        return json.dumps({"success": False, "error": "Unauthorized: System tool."})

    try:
        event = json.loads(event_json)
        DATABASE.record_event(cluster_name, event)
        return json.dumps({"success": True})

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})
