from typing import Dict, Optional, Type
from flux_mcp_server.clusters.interface import ClusterHandle, AuthContext
from flux_mcp_server.clusters.local import LocalFluxHandle

class ClusterRegistry:
    """
    A ClusterRegistry will hold one or more cluster contexts to submit work to.

    We need to hold state because we are listening for events OR receiving
    callbacks from clusters.
    """
    _instance = None
    
    def __init__(self):
        self._clusters: Dict[str, ClusterHandle] = {}

        # Map of 'type_name' -> Class
        self._handle_types: Dict[str, Type[ClusterHandle]] = {
            "local": LocalFluxHandle,
            # "ssh": SshFluxHandle (Future)
        }

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = ClusterRegistry()
        return cls._instance

    def register(self, name: str, type_str: str, config: dict) -> bool:
        """
        Creates and stores a new cluster handle.
        """
        if name in self._clusters:
            raise ValueError(f"Cluster '{name}' already exists.")
        
        handle_cls = self._handle_types.get(type_str)
        if not handle_cls:
            raise ValueError(f"Unknown handle type: {type_str}")

        # Instantiate
        handle = handle_cls(name, config)
        
        # Verify connection
        if not handle.connect():
             raise ConnectionError(f"Could not connect to {name} during registration.")

        self._clusters[name] = handle
        return True

    def remove(self, name: str) -> bool:
        if name in self._clusters:
            self._clusters[name].close()
            del self._clusters[name]
            return True
        return False

    def get_handle(self, name: str) -> Optional[ClusterHandle]:
        return self._clusters.get(name)

    def list_clusters(self) -> dict:
        """Returns metadata about registered clusters."""
        return {
            name: {"type": type(h).__name__, "config": h.config}
            for name, h in self._clusters.items()
        }

# Global Helper
def get_registry():
    return ClusterRegistry.get_instance()