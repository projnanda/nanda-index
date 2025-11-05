import os
import sys
import importlib

# Ensure module path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

export_mod = importlib.import_module('export_nanda_to_agntcy')


def test_parse_agent_id():
    assert export_mod.parse_agent_id('agentm-foo:v1.2.3') == ('agentm-foo', 'v1.2.3')
    assert export_mod.parse_agent_id('simple') == ('simple', 'v0')


def test_agent_to_oasf_record_minimal():
    agent_payload = {
        'agent_id': 'agentm-abc:v1',
        'agent_url': 'http://bridge/agentm-abc',
        'api_url': 'http://api/agentm-abc',
        'capabilities': ['math', 'chat'],
        'tags': ['alpha'],
        'last_update': '2025-01-01T00:00:00Z'
    }
    record = export_mod.agent_to_oasf_record(agent_payload)
    assert record['name'] == 'agentm-abc'
    assert record['version'] == 'v1'
    assert any(loc['type'] == 'bridge-url' for loc in record['locators'])
    assert any(loc['type'] == 'api-url' for loc in record['locators'])
    assert 'Capabilities:' in record['description']
    assert 'Tags:' in record['description']


def test_agent_to_oasf_record_mcp_extension():
    agent_payload = {
        'agent_id': 'agentm-mcp:v2',
        'agent_url': 'http://bridge/agentm-mcp',
        'api_url': 'cmd://docker?args=run -it image',
        'last_update': '2025-02-02T00:00:00Z'
    }
    record = export_mod.agent_to_oasf_record(agent_payload)
    assert any(ext['name'].endswith('/runtime/mcp') for ext in record['extensions'])
