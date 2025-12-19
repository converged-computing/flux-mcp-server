import json

from ..db.sqlite import JobDatabase

# This is initialized by the server's main.py
_DB_INSTANCE: JobDatabase = None


def init_query_tools(db_instance: JobDatabase):
    global _DB_INSTANCE
    _DB_INSTANCE = db_instance


# MCP Tools exposed to the Agent
# TODO (vsoch) these aren't tested


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

    return json.dumps({"job_id": record.job_id, "state": record.state, "history": record.events})


def find_failed_jobs(limit: int = 5) -> str:
    """Finds recent jobs that did not complete successfully."""
    # TODO (vsoch) Logic to query DB where exit_code != 0
    return json.dumps([])
