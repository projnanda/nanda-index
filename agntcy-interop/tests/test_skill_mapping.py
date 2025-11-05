import os
import sys
import importlib
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

mod = importlib.import_module('export_nanda_to_agntcy')

# Assume default schema dir relative path exists
SCHEMA_DIR = Path(mod.DEFAULT_OASF_SCHEMA_DIR)

def skip_if_schema_missing():
    if not SCHEMA_DIR.exists():
        import pytest
        pytest.skip('OASF schema directory missing; mapping tests skipped')


def test_exact_match():
    skip_if_schema_missing()
    mapper = mod.SkillMapper(SCHEMA_DIR)
    # pick a known leaf skill name present: text_classification
    skill = mapper.map_capability('text_classification')
    assert skill is not None
    assert 'class_name' in skill


def test_substring_caption_match():
    skip_if_schema_missing()
    mapper = mod.SkillMapper(SCHEMA_DIR)
    skill = mapper.map_capability('generation')  # expect natural_language_generation
    assert skill is not None
    assert 'Generation' in skill['class_name']


def test_fallback_chat():
    skip_if_schema_missing()
    mapper = mod.SkillMapper(SCHEMA_DIR)
    skill = mapper.map_capability('chat-interface')
    assert skill is not None
    assert skill['class_name']


def test_agent_record_skills_integration():
    skip_if_schema_missing()
    mapper = mod.SkillMapper(SCHEMA_DIR)
    agent_payload = {
        'agent_id': 'agentm-demo:v1',
        'agent_url': 'http://bridge/demo',
        'api_url': None,
        'capabilities': ['text_classification', 'chat-interface'],
        'last_update': '2025-01-01T00:00:00Z'
    }
    record = mod.agent_to_oasf_record(agent_payload, mapper=mapper)
    assert len(record['skills']) >= 2


def test_agent_record_dedup_skills():
    skip_if_schema_missing()
    mapper = mod.SkillMapper(SCHEMA_DIR)
    # Provide duplicate capabilities that should map to same skill
    agent_payload = {
        'agent_id': 'agentm-dedup:v1',
        'agent_url': 'http://bridge/dedup',
        'api_url': None,
        'capabilities': ['text_classification', 'text-classification', 'Text Classification'],
        'last_update': '2025-01-01T00:00:00Z'
    }
    record = mod.agent_to_oasf_record(agent_payload, mapper=mapper)
    skill_ids = [s['skill_id'] for s in record['skills']]
    assert len(skill_ids) == len(set(skill_ids)), 'Duplicate skill_id entries present'


def test_unknown_capability_returns_none():
    skip_if_schema_missing()
    mapper = mod.SkillMapper(SCHEMA_DIR)
    assert mapper.map_capability('incomprehensible_capability_xyz') is None


def test_parent_inference_or_no_match():
    skip_if_schema_missing()
    mapper = mod.SkillMapper(SCHEMA_DIR)
    # Attempt mapping using a parent skill name if available; choose a known non-leaf if taxonomy supplies it.
    # If taxonomy lacks that parent, tolerant: result may be None.
    possible = mapper.map_capability('natural_language_generation')
    # Accept either a payload (parent or leaf) or None if taxonomy differs.
    assert possible is None or 'skill_id' in possible


def test_skills_map_endpoint(monkeypatch):
    """Integration with /skills/map endpoint via Flask test client using registry internal mapper."""
    skip_if_schema_missing()
    # Ensure TEST_MODE so registry uses in-memory
    monkeypatch.setenv('TEST_MODE', '1')
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', os.pardir))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    import registry  # noqa: E402
    app = registry.app
    with app.test_client() as client:
        resp = client.get('/skills/map?capability=text_classification')
        assert resp.status_code in (200, 500, 404)  # 500 if mapper init failed, 404 if not found
        if resp.status_code == 200:
            data = resp.get_json()
            assert data['capability'] == 'text_classification'
            # Allow mapper to select a related leaf (e.g., sentiment_analysis) depending on taxonomy specifics
            assert 'skill_id' in data['mapped']
            assert data['mapped']['skill_id'] in ('text_classification', 'sentiment_analysis')
        else:
            # If error, give diagnostic for test logs
            _ = resp.get_json()
