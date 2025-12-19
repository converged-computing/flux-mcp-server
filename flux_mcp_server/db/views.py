import time
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select, update, and_

from flux_mcp_server.db.interface import DatabaseBackend
from flux_mcp_server.db.models import JobRecord, EventRecord
from flux_mcp_server.db.models import Base, JobModel, EventModel

class SQLAlchemyBackend(DatabaseBackend):
    """
    Common backend for a database. Sqlalchemy allows us to customize
    the URI and use the same interfaces.
    """
    def __init__(self, db_url: str):
        # e.g. "sqlite+aiosqlite:///server.db"
        # e.g. "postgresql+asyncpg://user:pass@host/db"
        self.engine = create_async_engine(db_url, echo=False)
        self.SessionLocal = async_sessionmaker(self.engine, expire_on_commit=False)
        self.dialect = self.engine.dialect.name

    async def initialize(self):
        # Create tables (IF NOT EXISTS is handled by metadata.create_all)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def close(self):
        await self.engine.dispose()

    async def record_event(self, cluster: str, event: Dict[str, Any]):
        """
        record_event is called via the events tool, so it is an MCP function
        that can be used by an agent or human to write an event to the peristent
        database backend here.
        """
        job_id = event.get("id")
        event_type = event.get("type")
        data = event.get("data", {})
        timestamp = event.get("t", time.time())

        async with self.SessionLocal() as session:
            async with session.begin():
                # 1. Log Event
                new_event = EventModel(
                    job_id=job_id,
                    cluster=cluster,
                    timestamp=timestamp,
                    event_type=event_type,
                    payload=data
                )
                session.add(new_event)

                # 2. Update Snapshot (The logic depends on event type)
                if event_type == "submit":
                    # For Upsert, we need a dialect-specific check or a generic "Select first" approach
                    # For simplicity and cross-DB support without complex imports, 
                    # we'll do a check-then-insert/update pattern.
                    # (High volume systems might want dialect specific UPSERTs)
                    
                    stmt = select(JobModel).where(
                        and_(JobModel.job_id == job_id, JobModel.cluster == cluster)
                    )
                    result = await session.execute(stmt)
                    job = result.scalar_one_or_none()

                    if not job:
                        job = JobModel(
                            job_id=job_id, cluster=cluster,
                            user=data.get("userid"),
                            state="submitted",
                            workdir=data.get("cwd", ""),
                            submit_time=timestamp,
                            last_updated=timestamp
                        )
                        session.add(job)
                    else:
                        job.state = "submitted"
                        job.last_updated = timestamp

                elif event_type == "state":
                    state_name = data.get("state_name")
                    stmt = update(JobModel).where(
                        and_(JobModel.job_id == job_id, JobModel.cluster == cluster)
                    ).values(state=state_name, last_updated=time.time())
                    
                    if state_name == "INACTIVE" and "status" in data:
                        stmt = stmt.values(exit_code=data["status"])
                    
                    await session.execute(stmt)

    async def get_job(self, cluster: str, job_id: int) -> Optional[JobRecord]:
        """
        Get job retrieves a job record from the database, which will have some number of
        associated events with it.
        """
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(JobModel).where(
                    and_(JobModel.job_id == job_id, JobModel.cluster == cluster)
                )
            )
            job = result.scalar_one_or_none()
            if job:
                # Convert ORM object to our standard Dataclass
                return JobRecord(
                    job_id=job.job_id,
                    cluster=job.cluster,
                    state=job.state,
                    user=job.user,
                    workdir=job.workdir,
                    exit_code=job.exit_code,
                    submit_time=job.submit_time,
                    last_updated=job.last_updated
                )
            return None

    async def get_event_history(self, cluster: str, job_id: int) -> List[EventRecord]:
        """
        Get event history will get event history for a job id. 
        We *could* pair this with getting a job, but I don't want to assume
        the user wants both at the same time.
        """
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(EventModel)
                .where(and_(EventModel.job_id == job_id, EventModel.cluster == cluster))
                .order_by(EventModel.timestamp.asc())
            )
            events = result.scalars().all()
            return [
                EventRecord(
                    timestamp=e.timestamp,
                    event_type=e.event_type,
                    payload=e.payload
                ) for e in events
            ]

    async def search_jobs(self, cluster: str = None, state: str = None, limit: int = 10) -> List[JobRecord]:
        """
        Search jobs does a search across jobs based on state and/or cluster.
        We can extend this to more things if needed. I haven't thought through
        the use cases.
        """
        async with self.SessionLocal() as session:
            stmt = select(JobModel)
            
            if cluster:
                stmt = stmt.where(JobModel.cluster == cluster)
            if state:
                stmt = stmt.where(JobModel.state == state)
            
            stmt = stmt.limit(limit)
            
            result = await session.execute(stmt)
            jobs = result.scalars().all()
            
            return [
                JobRecord(
                    job_id=j.job_id,
                    cluster=j.cluster,
                    state=j.state,
                    user=j.user,
                    workdir=j.workdir,
                    exit_code=j.exit_code,
                    submit_time=j.submit_time,
                    last_updated=j.last_updated
                ) for j in jobs
            ]