from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from .models import EventRecord, JobRecord


class DatabaseBackend(ABC):
    """
    Abstract interface for Flux MCP storage.
    Implementations could be SQLite, Postgres, Redis, etc.
    """

    @abstractmethod
    async def initialize(self):
        """Perform any setup (create tables, connections)."""
        pass

    @abstractmethod
    async def close(self):
        """Cleanup resources."""
        pass

    # Write Operations (Used by Scribe/EventsEngine)

    @abstractmethod
    async def record_event(self, cluster: str, event: Dict[str, Any]):
        """
        Ingest a raw event. Must update both the event log
        and the current job state snapshot atomically if possible.
        """
        pass

    # Read Operations (Used by MCP Tools / Agents)

    @abstractmethod
    async def get_job(self, cluster: str, job_id: int) -> Optional[JobRecord]:
        """Retrieve the current snapshot of a job."""
        pass

    @abstractmethod
    async def get_event_history(self, cluster: str, job_id: int) -> List[EventRecord]:
        """Retrieve the full event stream for a job."""
        pass

    @abstractmethod
    async def search_jobs(self, query: str, limit: int = 10) -> List[JobRecord]:
        """Find jobs based on criteria (e.g. 'state=FAILED')."""
        pass
