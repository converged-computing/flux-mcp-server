from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Protocol
from dataclasses import dataclass

@dataclass
class AuthContext:
    """
    Represents the credentials passed from the MCP client.

    There are two levels of auth interfaces, although they are different steps in the same flow.
    
    <incoming token> -> 
      <user authorized to use server?> (oauth) -> 
        <user authorized for specific cluster> ? -> 
          <submit to cluster as user>

    This interface is concerned with the last part, the user to cluster. We likely need
    Flux to manage the permissions for the handle. E.g., if the handle is discovered,
    it should not be possible to submit as a user without proper auth.
    """
    user_id: str
    token: Optional[str] = None
    provider: str = "local" # e.g., 'local', 'oauth', 'system'


class AuthProvider(Protocol):
    """
    Interface for verifying if a user is allowed to access a specific cluster.
    """
    def authorize(self, context: AuthContext, cluster_id: str) -> bool:
        return True


class ClusterHandle(ABC):
    """
    Abstract interface for any Flux-like cluster connection 
    (Local socket, SSH, REST API, RPC? etc).
    """
    def __init__(self, cluster_id: str, config: Dict[str, Any]):
        self.cluster_id = cluster_id
        self.config = config

    @abstractmethod
    def connect(self) -> bool:
        """Establishes connection (if stateful) or checks reachability."""
        pass

    @abstractmethod
    def submit(self, jobspec: str, auth: AuthContext) -> int:
        """Submits a job as the authenticated user."""
        pass

    @abstractmethod
    def cancel(self, job_id: int, auth: AuthContext) -> bool:
        """Cancels a job."""
        pass

    @abstractmethod
    def get_job_info(self, job_id: int, auth: AuthContext) -> Dict[str, Any]:
        """Gets job info."""
        pass

    @abstractmethod
    def close(self):
        """Cleanup resources."""
        pass