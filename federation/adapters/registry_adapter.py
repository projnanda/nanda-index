"""Local NANDA Registry Adapter - queries the local registry."""

from typing import Optional, Dict, Any
from .base_adapter import BaseRegistryAdapter
import httpx


class RegistryAdapter(BaseRegistryAdapter):
    """
    Adapter for local NANDA registry.
    
    Routes queries to the existing /agents/<agent_id> endpoint
    in the local registry.py service.
    """
    
    def __init__(self, registry_url: str = "http://localhost:6900"):
        super().__init__(registry_id="nanda")
        self.registry_url = registry_url.rstrip("/")
    
    async def query_agent(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """Query the local NANDA registry."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Try the /agents/<id> endpoint first (extended endpoint)
                response = await client.get(f"{self.registry_url}/agents/{agent_name}")
                
                if response.status_code == 404:
                    # Fallback to /lookup/<id> endpoint
                    print(f"[RegistryAdapter] /agents/{agent_name} returned 404, trying /lookup")
                    response = await client.get(f"{self.registry_url}/lookup/{agent_name}")
                    print(f"[RegistryAdapter] /lookup/{agent_name} returned {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"[RegistryAdapter] Found agent data: {list(data.keys())}")
                    return data
                
                print(f"[RegistryAdapter] Agent not found: {agent_name}")
                return None
                
        except Exception as e:
            print(f"[Registry] Error querying local registry: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def translate_to_nanda(self, source_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Local registry already returns NANDA format, so just ensure
        the schema fields are present.
        """
        # Ensure required fields
        result = {
            "agent_id": source_data.get("agent_id"),
            "registry_id": "nanda",
            "agent_name": source_data.get("agent_id") or source_data.get("agent_name"),
            "version": source_data.get("version", "v1.0.0"),
            "description": source_data.get("description", ""),
            "capabilities": source_data.get("capabilities", []),
            "agent_url": source_data.get("agent_url", ""),
            "api_url": source_data.get("api_url", ""),
            "last_updated": source_data.get("last_updated", source_data.get("last_update", "")),
            "schema_version": "nanda-v1",
            "source_schema": "nanda"
        }
        return result
    
    def get_registry_info(self) -> Dict[str, Any]:
        """Return metadata about local registry adapter."""
        info = super().get_registry_info()
        info.update({
            "registry_url": self.registry_url,
            "type": "local"
        })
        return info

