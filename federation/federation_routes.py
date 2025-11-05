"""Federation routing layer - integrates with Flask registry.py."""

import os
from flask import jsonify, request
from typing import Dict, Any, Optional, Tuple
import asyncio

# Import adapters
from .adapters.registry_adapter import RegistryAdapter
try:
    from .adapters.agntcy_adapter import AGNTCYAdapter
    AGNTCY_AVAILABLE = True
except Exception as e:
    AGNTCY_AVAILABLE = False
    print(f"[Federation] AGNTCY adapter not available: {e}")


class FederationRouter:
    """
    Federation routing layer for NANDA Index.
    
    Routes agent lookups to appropriate adapters based on identifier prefix:
    - @agntcy:agent-name → AGNTCY adapter
    - @openai:plugin-name → OpenAI adapter (future)
    - agent-name → Local NANDA registry
    """
    
    def __init__(self):
        self.adapters: Dict[str, Any] = {}
        self._init_adapters()
    
    def _init_adapters(self):
        """Initialize available adapters based on configuration."""
        
        # Local NANDA registry adapter (always available)
        # Use PORT env var to construct the correct URL if running on non-standard port
        port = os.getenv("PORT", "6900")
        registry_url = os.getenv("REGISTRY_URL", f"http://localhost:{port}")
        self.adapters["nanda"] = RegistryAdapter(registry_url)
        print(f"[Federation] ✅ Local registry adapter initialized: {registry_url}")
        
        # AGNTCY adapter (optional, based on env vars)
        agntcy_ads_url = os.getenv("AGNTCY_ADS_URL")
        if agntcy_ads_url and AGNTCY_AVAILABLE:
            try:
                dirctl_path = os.getenv("DIRCTL_PATH", "/opt/homebrew/bin/dirctl")
                oasf_schema_dir = os.getenv("OASF_SCHEMA_DIR")
                
                self.adapters["agntcy"] = AGNTCYAdapter(
                    server_address=agntcy_ads_url,
                    dirctl_path=dirctl_path,
                    oasf_schema_dir=oasf_schema_dir
                )
                print(f"[Federation] ✅ AGNTCY adapter initialized: {agntcy_ads_url}")
            except Exception as e:
                print(f"[Federation] ⚠️  AGNTCY adapter failed to initialize: {e}")
        elif agntcy_ads_url and not AGNTCY_AVAILABLE:
            print("[Federation] ⚠️  AGNTCY_ADS_URL set but adapter not available")
    
    def parse_agent_identifier(self, agent_id: str) -> Tuple[str, str]:
        """
        Parse agent identifier into (registry_id, agent_name).
        
        Examples:
        - "@agntcy:helper-agent" → ("agntcy", "helper-agent")
        - "financial-analyzer" → ("nanda", "financial-analyzer")
        """
        # Remove leading @ if present
        if agent_id.startswith("@"):
            agent_id = agent_id[1:]
        
        # Check for registry prefix
        if ":" in agent_id:
            parts = agent_id.split(":", 1)
            if len(parts) == 2:
                return parts[0], parts[1]
        
        # Default to local NANDA registry
        return "nanda", agent_id
    
    async def lookup_federated(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """
        Perform federated lookup across registries.
        
        Args:
            agent_id: Agent identifier (with or without @registry: prefix)
            
        Returns:
            NANDA AgentFacts format dict, or None if not found
        """
        registry_id, agent_name = self.parse_agent_identifier(agent_id)
        
        print(f"[Federation] Lookup request: {agent_id}")
        print(f"[Federation] Routing to: {registry_id}, agent: {agent_name}")
        print(f"[Federation] Available adapters: {list(self.adapters.keys())}")
        
        # Get adapter
        adapter = self.adapters.get(registry_id)
        if not adapter:
            print(f"[Federation] ❌ Unknown registry: {registry_id}")
            return None
        
        print(f"[Federation] Using adapter: {adapter.__class__.__name__}")
        
        # Perform lookup
        try:
            result = await adapter.lookup(agent_name)
            print(f"[Federation] Adapter returned: {result is not None}")
        except Exception as e:
            print(f"[Federation] ❌ Adapter error: {e}")
            import traceback
            traceback.print_exc()
            return None
        
        if result:
            print(f"[Federation] ✅ Found agent: {agent_id}")
        else:
            print(f"[Federation] ❌ Agent not found: {agent_id}")
        
        return result
    
    def list_registries(self) -> Dict[str, Any]:
        """List all available registries and their status."""
        return {
            "registries": [
                adapter.get_registry_info() 
                for adapter in self.adapters.values()
            ],
            "count": len(self.adapters)
        }


# Global router instance
_router: Optional[FederationRouter] = None


def get_router() -> FederationRouter:
    """Get or create the global federation router."""
    global _router
    if _router is None:
        _router = FederationRouter()
    return _router


def register_federation_routes(app):
    """
    Register federation endpoints with Flask app.
    
    Adds:
    - GET /federation/lookup/<agent_id>
    - GET /federation/registries
    """
    
    @app.route('/federation/lookup/<agent_id>', methods=['GET'])
    def federation_lookup(agent_id):
        """Federated agent lookup endpoint."""
        router = get_router()
        
        # Run async lookup in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(router.lookup_federated(agent_id))
        finally:
            loop.close()
        
        if not result:
            return jsonify({"error": f"Agent not found: {agent_id}"}), 404
        
        return jsonify(result)
    
    @app.route('/federation/registries', methods=['GET'])
    def federation_registries():
        """List all federated registries."""
        router = get_router()
        return jsonify(router.list_registries())
    
    print("[Federation] ✅ Federation routes registered")
    print("[Federation]    - GET /federation/lookup/<agent_id>")
    print("[Federation]    - GET /federation/registries")

