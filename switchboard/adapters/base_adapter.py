"""Base adapter interface for registry adapters."""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List


class BaseRegistryAdapter(ABC):
    """
    Abstract base class for registry adapters.
    
    Each adapter is responsible for:
    1. Querying its specific registry (AGNTCY, OpenAI, etc.)
    2. Translating the response to NANDA AgentFacts format
    3. Handling errors gracefully
    """
    
    def __init__(self, registry_id: str):
        self.registry_id = registry_id
    
    @abstractmethod
    async def query_agent(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """
        Query the registry for an agent by name.
        
        Args:
            agent_name: The agent name/identifier to search for
            
        Returns:
            Raw agent data from the source registry, or None if not found
        """
        pass
    
    @abstractmethod
    def translate_to_nanda(self, source_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Translate source registry format to NANDA AgentFacts format.
        
        Args:
            source_data: Raw agent data from source registry
            
        Returns:
            Dict in NANDA AgentFacts format with fields:
            - agent_id: str
            - registry_id: str
            - agent_name: str
            - version: str
            - description: str
            - capabilities: List[str]
            - agent_url: str
            - api_url: str
            - last_updated: str
            - schema_version: str
            - source_schema: str
        """
        pass
    
    async def lookup(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """
        High-level lookup method: query + translate.
        
        Args:
            agent_name: Agent name to lookup
            
        Returns:
            NANDA AgentFacts format dict, or None if not found
        """
        source_data = await self.query_agent(agent_name)
        if not source_data:
            return None
        return self.translate_to_nanda(source_data)
    
    def get_registry_info(self) -> Dict[str, Any]:
        """Return metadata about this adapter/registry."""
        return {
            "registry_id": self.registry_id,
            "adapter_type": self.__class__.__name__,
            "status": "active"
        }

