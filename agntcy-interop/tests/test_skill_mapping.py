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
