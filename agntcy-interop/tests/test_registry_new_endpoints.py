import os
import sys
import importlib
import pytest

# Enable TEST_MODE before importing registry
os.environ['TEST_MODE'] = '1'

interop_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
repo_root = os.path.abspath(os.path.join(interop_root, os.pardir))
for p in (interop_root, repo_root):
    if p not in sys.path:
        sys.path.insert(0, p)

registry_module = importlib.import_module('registry')
app = registry_module.app

@pytest.fixture
def client():
    with app.test_client() as c:
        yield c


def register_sample(client, agent_id='agentm-new-1', agent_url='http://example.com/bridge', api_url='http://example.com/api'):
    return client.post('/register', json={'agent_id': agent_id, 'agent_url': agent_url, 'api_url': api_url})


def test_health_endpoint(client):
    resp = client.get('/health')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['status'] == 'ok'


def test_stats_counts(client):
    register_sample(client, agent_id='agentm-stats-1')
    register_sample(client, agent_id='agentm-stats-2')
    resp = client.get('/stats')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['total_agents'] >= 2


def test_agent_get_and_status_update(client):
    register_sample(client, agent_id='agentm-status-1')
    # Update status
    upd = client.put('/agents/agentm-status-1/status', json={'alive': True, 'capabilities': ['chat'], 'tags': ['test']})
    assert upd.status_code == 200
    # Fetch
    got = client.get('/agents/agentm-status-1')
    assert got.status_code == 200
    payload = got.get_json()
    assert payload['alive'] is True
    assert 'chat' in payload['capabilities']
    assert 'test' in payload['tags']


def test_search_filters(client):
    register_sample(client, agent_id='agentm-search-1')
    client.put('/agents/agentm-search-1/status', json={'alive': True, 'capabilities': ['math'], 'tags': ['alpha']})
    # Query by substring
    r1 = client.get('/search?q=search')
    assert any(a['agent_id'] == 'agentm-search-1' for a in r1.get_json())
    # Query by capabilities
    r2 = client.get('/search?capabilities=math')
    assert any(a['agent_id'] == 'agentm-search-1' for a in r2.get_json())
    # Query by tags
    r3 = client.get('/search?tags=alpha')
    assert any(a['agent_id'] == 'agentm-search-1' for a in r3.get_json())


def test_delete_agent(client):
    register_sample(client, agent_id='agentm-delete-1')
    d = client.delete('/agents/agentm-delete-1')
    assert d.status_code == 200
    # Ensure gone
    g = client.get('/agents/agentm-delete-1')
    assert g.status_code == 404


def test_mcp_servers_stub(client):
    # Register one with pseudo capability
    register_sample(client, agent_id='mcp-server-1')
    client.put('/agents/mcp-server-1/status', json={'alive': True, 'capabilities': ['mcp-server']})
    resp = client.get('/mcp_servers')
    servers = resp.get_json()
    assert any(s['agent_id'] == 'mcp-server-1' for s in servers)
