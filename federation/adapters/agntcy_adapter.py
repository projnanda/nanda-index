"""AGNTCY Registry Adapter - queries AGNTCY ADS via gRPC SDK."""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from .base_adapter import BaseRegistryAdapter

# AGNTCY SDK imports
try:
    from agntcy.dir_sdk.client import Config, Client
    from agntcy.dir_sdk.models import search_v1, core_v1
    from google.protobuf.json_format import MessageToDict
    AGNTCY_SDK_AVAILABLE = True
except ImportError:
    AGNTCY_SDK_AVAILABLE = False
    print("[WARN] AGNTCY SDK not available. Install with: pip install agntcy-dir-sdk")

# Import SkillMapper from agntcy-interop
try:
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "agntcy-interop"))
    from batch.export_nanda_to_agntcy import SkillMapper
    SKILL_MAPPER_AVAILABLE = True
except ImportError:
    SKILL_MAPPER_AVAILABLE = False
    print("[WARN] SkillMapper not available. Skill taxonomy mapping disabled.")


class AGNTCYAdapter(BaseRegistryAdapter):
    """
    Adapter for AGNTCY Agent Directory Service (ADS).
    
    Features:
    - Real-time queries to ADS via gRPC
    - OASF to NANDA format translation
    - Skill taxonomy mapping using SkillMapper
    """
    
    def __init__(
        self, 
        server_address: str = "localhost:8888",
        dirctl_path: str = "/opt/homebrew/bin/dirctl",
        oasf_schema_dir: Optional[str] = None
    ):
        super().__init__(registry_id="agntcy")
        
        if not AGNTCY_SDK_AVAILABLE:
            raise RuntimeError(
                "AGNTCY SDK is required but not installed. "
                "Install with: pip install agntcy-dir-sdk"
            )
        
        self.server_address = server_address
        self.dirctl_path = dirctl_path
        
        # Initialize AGNTCY SDK client
        config = Config(
            server_address=server_address,
            dirctl_path=dirctl_path
        )
        self.client = Client(config)
        print(f"✅ AGNTCY SDK Client initialized at {server_address}")
        
        # Initialize SkillMapper for taxonomy mapping
        self.skill_mapper = None
        if SKILL_MAPPER_AVAILABLE:
            # Clone taxonomy inside the project for self-contained setup
            default_schema_path = Path(__file__).parent.parent.parent / ".oasf-taxonomy" / "schema"
            schema_dir = oasf_schema_dir or os.environ.get(
                "OASF_SCHEMA_DIR", 
                str(default_schema_path)
            )
            schema_path = Path(schema_dir)
            if schema_path.exists():
                try:
                    self.skill_mapper = SkillMapper(schema_path)
                    print(f"✅ SkillMapper initialized with taxonomy")
                    print(f"   → {len(self.skill_mapper.leaf_skills)} skills loaded")
                except Exception as e:
                    print(f"[WARN] SkillMapper initialization failed: {e}")
    
    async def query_agent(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """
        Query AGNTCY Directory for an agent by name.
        
        Uses the AGNTCY SDK to:
        1. Search for agent by name
        2. Pull the full OASF record
        3. Return as dict
        """
        try:
            # Build search query
            search_query = search_v1.RecordQuery(
                type=search_v1.RecordQueryType.RECORD_QUERY_TYPE_NAME,
                value=agent_name
            )
            
            search_request = search_v1.SearchRequest(
                queries=[search_query],
                limit=1
            )
            
            # Perform search (blocking SDK call wrapped in asyncio)
            search_result_list = await asyncio.to_thread(
                self.client.search, 
                search_request
            )
            
            # Convert to list
            search_results = list(search_result_list)
            
            if not search_results:
                print(f"[AGNTCY] Agent '{agent_name}' not found")
                return None
            
            # Pull the record by CID
            fetched_cid = search_results[0].record_cid
            refs = [core_v1.RecordRef(cid=fetched_cid)]
            pulled_records = self.client.pull(refs)
            
            if not pulled_records:
                print(f"[AGNTCY] Failed to pull record for CID {fetched_cid}")
                return None
            
            # Convert to dict
            pulled_record = pulled_records[0]
            record_dict = MessageToDict(pulled_record, preserving_proto_field_name=True)
            
            # Unwrap 'data' if present
            oasf_data = record_dict.get("data", record_dict)
            
            print(f"[AGNTCY] ✅ Retrieved agent: {agent_name}")
            return oasf_data
            
        except Exception as e:
            print(f"[AGNTCY] ❌ Error querying agent '{agent_name}': {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def translate_to_nanda(self, oasf_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Translate OASF format to NANDA AgentFacts format.
        
        Includes skill taxonomy mapping if SkillMapper is available.
        """
        name = oasf_data.get("name", "unknown")
        version = oasf_data.get("version", "v0")
        agent_id = f"@{self.registry_id}:{name}"
        
        # Extract locators
        locators = oasf_data.get("locators", [])
        agent_url = ""
        api_url = ""
        
        for locator in locators:
            loc_type = locator.get("type", "").lower() if isinstance(locator, dict) else ""
            url = locator.get("url", "") if isinstance(locator, dict) else ""
            
            if "source" in loc_type or "github" in loc_type:
                agent_url = url
            elif "api" in loc_type or "service" in loc_type:
                api_url = url
        
        # Fallback to first locator if no specific type matched
        if not agent_url and locators:
            first = locators[0]
            agent_url = first.get("url", "") if isinstance(first, dict) else ""
        
        # Map skills to capabilities with taxonomy
        capabilities = self._map_skills_to_capabilities(oasf_data.get("skills", []))
        
        return {
            "agent_id": agent_id,
            "registry_id": self.registry_id,
            "agent_name": name,
            "version": version,
            "description": oasf_data.get("description", ""),
            "capabilities": capabilities,
            "agent_url": agent_url,
            "api_url": api_url,
            "last_updated": oasf_data.get("created_at", datetime.now().isoformat()),
            "schema_version": "nanda-v1",
            "source_schema": "oasf",
            "oasf_schema_version": oasf_data.get("schema_version", "unknown")
        }
    
    def _map_skills_to_capabilities(self, skills: List[Dict[str, Any]]) -> List[Any]:
        """
        Map OASF skills to NANDA capabilities using taxonomy.
        
        If SkillMapper is available, returns full taxonomy dicts.
        Otherwise, returns simple skill name strings.
        """
        capabilities = []
        seen = set()
        
        for skill in skills:
            skill_name = skill.get("name", "") if isinstance(skill, dict) else ""
            if not skill_name:
                continue
            
            # Try taxonomy mapping first
            if self.skill_mapper:
                # Extract leaf skill name (after last /)
                leaf_name = skill_name.split("/")[-1] if "/" in skill_name else skill_name
                mapped = self.skill_mapper.map_capability(leaf_name)
                
                if mapped:
                    # Return full taxonomy dict
                    cap_id = mapped.get('skill_id')
                    if cap_id and cap_id not in seen:
                        capabilities.append(mapped)  # ← Return full dict!
                        seen.add(cap_id)
                        continue
            
            # Fallback: use simple name extraction
            if "/" in skill_name:
                skill_name = skill_name.split("/")[-1]
            
            if skill_name and skill_name not in seen:
                capabilities.append(skill_name)
                seen.add(skill_name)
        
        return capabilities
    
    def get_registry_info(self) -> Dict[str, Any]:
        """Return metadata about AGNTCY adapter."""
        info = super().get_registry_info()
        info.update({
            "server_address": self.server_address,
            "skill_mapping": self.skill_mapper is not None,
            "sdk_available": AGNTCY_SDK_AVAILABLE
        })
        return info

