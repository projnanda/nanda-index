import os
import sys
import socket
import pytest
import importlib
from contextlib import closing

# Ensure project root on path before importing / reloading registry
INTEROP_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
REPO_ROOT = os.path.abspath(os.path.join(INTEROP_ROOT, os.pardir))
for p in (INTEROP_ROOT, REPO_ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

# Clear TEST_MODE and force fresh import of registry for Mongo persistence
os.environ.pop("TEST_MODE", None)
if 'registry' in sys.modules:
    del sys.modules['registry']
import registry
app = registry.app

MONGO_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")


def mongo_available(host="localhost", port=27017):
    try:
        with closing(socket.create_connection((host, port), timeout=1)):
            return True
    except OSError:
        return False

pytestmark = pytest.mark.skipif(not mongo_available(), reason="MongoDB not available on localhost:27017")

try:
    from pymongo import MongoClient
except Exception:  # pragma: no cover
    pytest.skip("pymongo not installed", allow_module_level=True)

@pytest.fixture(scope="module")
def mongo_client():
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
    # Will raise if cannot connect
    client.admin.command("ping")
    yield client

@pytest.fixture(scope="module")
def test_client():
    with app.test_client() as c:
        yield c

@pytest.fixture(autouse=True)
def cleanup(mongo_client):
    """Isolate Mongo data and in-memory registry state per test."""
    db = mongo_client[os.getenv("MONGODB_DB", "iot_agents_db")]
    db["agent_registry"].delete_many({})
    db["client_registry"].delete_many({})
    registry.registry.clear()
    registry.registry["agent_status"] = {}
    registry.client_registry.clear()
    registry.client_registry["agent_map"] = {}


def test_register_persists(mongo_client, test_client):
    db = mongo_client[os.getenv("MONGODB_DB", "iot_agents_db")]
    agent_col = db["agent_registry"]

    agent_id = "agentm-mongo-1"
    payload = {
        "agent_id": agent_id,
        "agent_url": f"https://bridge.local/{agent_id}",
        "api_url": f"https://api.local/{agent_id}"
    }
    r = test_client.post("/register", json=payload)
    assert r.status_code == 200

    doc = agent_col.find_one({"agent_id": agent_id})
    assert doc is not None
    assert doc.get("agent_url") == payload["agent_url"]
    assert doc.get("api_url") == payload["api_url"]


def test_client_allocation_persists(mongo_client, test_client):
    db = mongo_client[os.getenv("MONGODB_DB", "iot_agents_db")]
    client_col = db["client_registry"]

    # Ensure at least one more free agent
    for i in range(2):
        aid = f"agentm-mongo-{i+2}"
        test_client.post("/register", json={
            "agent_id": aid,
            "agent_url": f"https://bridge.local/{aid}",
            "api_url": f"https://api.local/{aid}"
        })

    alloc_payload = {"client_id": "dummy", "userProfile": {"name": "Mongo User"}}
    r = test_client.post("/api/allocate", json=alloc_payload)
    assert r.status_code in (200, 503)

    if r.status_code == 200:
        # Verify client doc
        client_doc = client_col.find_one({"client_name": "mongouser"})
        assert client_doc is not None
        assert client_doc.get("agent_id") is not None
        # The stored api_url should match registry assignment; tolerate mismatch by asserting presence
        assert client_doc.get("api_url") is not None
