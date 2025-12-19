import json
from ..db.sqlite import JobDatabase

# This is initialized by the server's main.py
_DB_INSTANCE: JobDatabase = None

def init_query_tools(db_instance: JobDatabase):
    """Dependency Injection for the global DB"""
    global _DB_INSTANCE
    _DB_INSTANCE = db_instance

# --------------------------------------------------------
# MCP Tools exposed to the Agent
# --------------------------------------------------------

def query_job_history(job_id: int) -> str:
    """
    Retrieve the historical record of a job from the database.
    Useful for analyzing jobs that have already finished/purged.
    """
    if not _DB_INSTANCE:
        return json.dumps({"error": "Database not initialized"})

    record = _DB_INSTANCE.get_job(job_id)
    if not record:
        return json.dumps({"error": "Job not found in history"})
        
    return json.dumps({
        "job_id": record.job_id,
        "state": record.state,
        "history": record.events
    })

def find_failed_jobs(limit: int = 5) -> str:
    """Finds recent jobs that did not complete successfully."""
    # Logic to query DB where exit_code != 0
    return json.dumps([...])