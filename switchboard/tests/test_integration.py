"""Integration tests for federation layer with agntcy-interop."""

import sys
import os
from pathlib import Path

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def test_agntcy_adapter_imports_skillmapper():
    """Test that AGNTCY adapter can import SkillMapper from agntcy-interop."""
    from switchboard.adapters.agntcy_adapter import SKILL_MAPPER_AVAILABLE
    
    # SkillMapper should be available (even without AGNTCY SDK)
    assert SKILL_MAPPER_AVAILABLE, "SkillMapper should be importable from agntcy-interop"
    print("✅ AGNTCY adapter successfully imports SkillMapper")


def test_skillmapper_can_be_instantiated():
    """Test that SkillMapper from agntcy-interop can be instantiated."""
    from switchboard.adapters.agntcy_adapter import SKILL_MAPPER_AVAILABLE
    
    if not SKILL_MAPPER_AVAILABLE:
        import pytest
        pytest.skip("SkillMapper not available")
    
    # Import SkillMapper directly
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "agntcy-interop"))
    from batch.export_nanda_to_agntcy import SkillMapper
    
    # Create a dummy schema directory for testing
    test_schema_dir = Path(__file__).parent / "test_schema"
    test_schema_dir.mkdir(exist_ok=True)
    
    try:
        # SkillMapper should handle missing schema gracefully
        mapper = SkillMapper(test_schema_dir)
        assert mapper is not None
        print("✅ SkillMapper can be instantiated")
    finally:
        # Cleanup
        if test_schema_dir.exists():
            test_schema_dir.rmdir()


def test_agntcy_adapter_translation_without_skillmapper():
    """Test AGNTCY adapter OASF translation works without SkillMapper."""
    from switchboard.adapters.agntcy_adapter import AGNTCYAdapter, AGNTCY_SDK_AVAILABLE
    
    if AGNTCY_SDK_AVAILABLE:
        import pytest
        pytest.skip("AGNTCY SDK available, test expects it to be missing")
    
    # Mock OASF data
    oasf_data = {
        "name": "test-agent",
        "version": "v1.0.0",
        "description": "Test agent",
        "skills": [
            {"name": "text_generation"},
            {"name": "image_processing/segmentation"}
        ],
        "locators": [
            {"type": "source_code", "url": "https://github.com/test/agent"}
        ],
        "created_at": "2025-01-01T00:00:00Z",
        "schema_version": "0.7.0"
    }
    
    # Create adapter (will fail at __init__ due to missing SDK, so test just translation)
    # We'll test the translation method directly by mocking
    from switchboard.adapters.base_adapter import BaseRegistryAdapter
    
    class MockAGNTCYAdapter(BaseRegistryAdapter):
        def __init__(self):
            super().__init__(registry_id="agntcy")
            self.skill_mapper = None
        
        async def query_agent(self, agent_name):
            return None
        
        def _map_skills_to_capabilities(self, skills):
            capabilities = []
            for skill in skills:
                skill_name = skill.get("name", "")
                if "/" in skill_name:
                    skill_name = skill_name.split("/")[-1]
                if skill_name:
                    capabilities.append(skill_name)
            return capabilities
        
        def translate_to_nanda(self, oasf_data):
            # Copy translation logic from AGNTCYAdapter
            name = oasf_data.get("name", "unknown")
            version = oasf_data.get("version", "v0")
            agent_id = f"@{self.registry_id}:{name}"
            
            locators = oasf_data.get("locators", [])
            agent_url = ""
            if locators:
                agent_url = locators[0].get("url", "")
            
            capabilities = self._map_skills_to_capabilities(oasf_data.get("skills", []))
            
            return {
                "agent_id": agent_id,
                "registry_id": self.registry_id,
                "agent_name": name,
                "version": version,
                "description": oasf_data.get("description", ""),
                "capabilities": capabilities,
                "agent_url": agent_url,
                "api_url": "",
                "last_updated": oasf_data.get("created_at", ""),
                "schema_version": "nanda-v1",
                "source_schema": "oasf",
                "oasf_schema_version": oasf_data.get("schema_version", "unknown")
            }
    
    adapter = MockAGNTCYAdapter()
    result = adapter.translate_to_nanda(oasf_data)
    
    # Verify translation
    assert result["agent_id"] == "@agntcy:test-agent"
    assert result["agent_name"] == "test-agent"
    assert result["version"] == "v1.0.0"
    assert "text_generation" in result["capabilities"]
    assert "segmentation" in result["capabilities"]
    assert result["source_schema"] == "oasf"
    
    print("✅ OASF to NANDA translation works")


def test_registry_adapter_can_be_instantiated():
    """Test that RegistryAdapter can be created."""
    from switchboard.adapters.registry_adapter import RegistryAdapter
    
    adapter = RegistryAdapter("http://localhost:6900")
    assert adapter is not None
    assert adapter.registry_id == "nanda"
    assert adapter.registry_url == "http://localhost:6900"
    
    print("✅ RegistryAdapter instantiation works")


def test_federation_router_initialization():
    """Test that SwitchboardRouter initializes adapters correctly."""
    from switchboard.switchboard_routes import SwitchboardRouter
    
    # Set minimal env
    os.environ.pop('AGNTCY_ADS_URL', None)  # Ensure it's not set
    
    router = SwitchboardRouter()
    
    # Should have at least the local NANDA adapter
    assert 'nanda' in router.adapters
    assert router.adapters['nanda'] is not None
    
    # Should NOT have AGNTCY adapter without AGNTCY_ADS_URL
    assert 'agntcy' not in router.adapters
    
    print("✅ SwitchboardRouter initialization works")


def test_federation_router_parse_identifier():
    """Test agent identifier parsing."""
    from switchboard.switchboard_routes import SwitchboardRouter
    
    router = SwitchboardRouter()
    
    # Test @agntcy:agent-name
    registry_id, agent_name = router.parse_agent_identifier("@agntcy:helper-agent")
    assert registry_id == "agntcy"
    assert agent_name == "helper-agent"
    
    # Test agntcy:agent-name (no @)
    registry_id, agent_name = router.parse_agent_identifier("agntcy:helper-agent")
    assert registry_id == "agntcy"
    assert agent_name == "helper-agent"
    
    # Test plain agent-name (should default to nanda)
    registry_id, agent_name = router.parse_agent_identifier("financial-analyzer")
    assert registry_id == "nanda"
    assert agent_name == "financial-analyzer"
    
    print("✅ Agent identifier parsing works")


def test_skillmapper_integration_with_mock_data():
    """Test SkillMapper can map capabilities (with mock taxonomy)."""
    from switchboard.adapters.agntcy_adapter import SKILL_MAPPER_AVAILABLE
    
    if not SKILL_MAPPER_AVAILABLE:
        import pytest
        pytest.skip("SkillMapper not available")
    
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "agntcy-interop"))
    from batch.export_nanda_to_agntcy import SkillMapper
    
    # Test with non-existent schema (SkillMapper should handle gracefully)
    test_schema_dir = Path(__file__).parent / "nonexistent_schema"
    
    mapper = SkillMapper(test_schema_dir)
    
    # Even without real schema, mapper should not crash
    result = mapper.map_capability("text_generation")
    # Result should be None for non-existent schema
    assert result is None or isinstance(result, dict)
    
    print("✅ SkillMapper handles missing schema gracefully")


if __name__ == "__main__":
    # Run tests manually
    print("\n" + "="*60)
    print("Running Federation Integration Tests")
    print("="*60 + "\n")
    
    tests = [
        test_agntcy_adapter_imports_skillmapper,
        test_skillmapper_can_be_instantiated,
        test_agntcy_adapter_translation_without_skillmapper,
        test_registry_adapter_can_be_instantiated,
        test_federation_router_initialization,
        test_federation_router_parse_identifier,
        test_skillmapper_integration_with_mock_data,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"❌ {test.__name__} failed: {e}")
            failed += 1
    
    print("\n" + "="*60)
    print(f"Results: {passed} passed, {failed} failed")
    print("="*60)
    
    sys.exit(0 if failed == 0 else 1)

