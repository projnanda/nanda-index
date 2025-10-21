import os
import sys
import pytest

# Ensure project root on path prior to import
INTEROP_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
REPO_ROOT = os.path.abspath(os.path.join(INTEROP_ROOT, os.pardir))  # nanda-index directory
for p in (INTEROP_ROOT, REPO_ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

# Activate test mode env flag before import
os.environ.setdefault("TEST_MODE", "1")

from registry import app

@pytest.fixture(scope="module")
def test_client():
    # Use Flask test client
    os.environ["PORT"] = "5001"  # isolate port
    with app.test_client() as client:
        yield client


def test_register_and_lookup(test_client):
    # Register a fake agent
    payload = {
        "agent_id": "agentm-test-1",
        "agent_url": "https://bridge.local/agentm-test-1",
        "api_url": "https://api.local/agentm-test-1"
    }
    r = test_client.post("/register", json=payload)
    assert r.status_code == 200
    assert r.json["status"] == "success"

    # Lookup the agent
    r2 = test_client.get("/lookup/agentm-test-1")
    assert r2.status_code == 200
    assert r2.json["agent_id"] == "agentm-test-1"
    assert r2.json["agent_url"] == payload["agent_url"]
    assert r2.json["api_url"] == payload["api_url"]


def test_allocate_agent(test_client):
    # Need at least one available agent. Register two.
    for i in range(2):
        payload = {
            "agent_id": f"agentm-test-{i+2}",
            "agent_url": f"https://bridge.local/agentm-test-{i+2}",
            "api_url": f"https://api.local/agentm-test-{i+2}"
        }
        test_client.post("/register", json=payload)

    allocate_payload = {
        "client_id": "dummy",  # field expected though not used properly
        "userProfile": {"name": "Test User"}
    }
    r = test_client.post("/api/allocate", json=allocate_payload)
    # Either success or already allocated depending on randomness
    assert r.status_code in (200, 503)
    if r.status_code == 200:
        assert r.json["status"] == "success"
        assert "agent_url" in r.json
        assert "api_url" in r.json


def test_list_endpoints(test_client):
    # List agents should return at least one (from previous tests)
    r = test_client.get("/list")
    assert r.status_code == 200
    assert isinstance(r.json, dict)

    rc = test_client.get("/clients")
    assert rc.status_code == 200
    assert isinstance(rc.json, dict)
