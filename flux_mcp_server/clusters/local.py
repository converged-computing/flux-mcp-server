import json

import flux
import flux.job

from flux_mcp_server.clusters.interface import AuthContext, ClusterHandle


class LocalFluxHandle(ClusterHandle):
    """
    A local Flux Handle means discovering a cluster locally.

    This is (likely) primarily for testing, and assumes the MCP server
    is running directly on the cluster of interest.
    """

    def __init__(self, cluster_id: str, config: dict):
        super().__init__(cluster_id, config)
        # If unset (None) uses default local
        self.uri = config.get("uri")
        self._handle = None

    def connect(self) -> bool:
        try:
            if self.uri:
                self._handle = flux.Flux(self.uri)
            else:
                self._handle = flux.Flux()
            return True
        except Exception as e:
            print(f"Failed to connect to local flux: {e}")
            return False

    def _get_h(self):
        # Lazy reconnect if needed
        if self._handle is None:
            self.connect()
        return self._handle

    def submit(self, jobspec: str, auth: AuthContext) -> int:
        # 1. Auth Check (Simple single-user ownership check)
        # In a real system, you might check: if auth.user_id != os.getuid()...
        print(f"DEBUG: Submitting to {self.cluster_id} as user {auth.user_id}")

        # 2. Parse
        if isinstance(jobspec, str):
            spec = json.loads(jobspec)
        else:
            spec = jobspec

        # 3. Submit
        jobid = flux.job.submit(self._get_h(), spec)
        return int(jobid)

    def cancel(self, job_id: int, auth: AuthContext) -> bool:
        print(f"DEBUG: Canceling job {job_id} on {self.cluster_id}")
        try:
            flux.job.cancel(self._get_h(), int(job_id))
            return True
        except Exception:
            return False

    def get_job_info(self, job_id: int, auth: AuthContext) -> dict:
        info = flux.job.get_job_info(self._get_h(), int(job_id))
        # Serialize essential fields
        return {"id": int(info.id), "state": info.state_name, "user": info.userid, "cwd": info.cwd}

    def close(self):
        self._handle = None
