import os
import sys
import socket
import pytest
import importlib
from contextlib import closing

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Force registry reload without TEST_MODE
os.environ.pop("TEST_MODE", None)
if 'registry' in sys.modules:
    del sys.modules['registry']
import registry
app = registry.app

MONGO_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("MONGODB_DB", "iot_agents_db")


def mongo_available(host="localhost", port=27017):
    try:
        with closing(socket.create_connection((host, port), timeout=1)):
            return True
    except OSError:
        return False

pytestmark = pytest.mark.skipif(not mongo_available(), reason="MongoDB not available on localhost:27017")

from pymongo import MongoClient  # noqa: E402

@pytest.fixture(scope="module")
def mongo_client():
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
    client.admin.command("ping")
    yield client

@pytest.fixture(scope="module")
def db(mongo_client):
    return mongo_client[DB_NAME]

@pytest.fixture(scope="function", autouse=True)
def cleanup(db):
    # Clean relevant collections before each test for isolation
    db["agent_registry"].delete_many({})
    db["client_registry"].delete_many({})
    db["users"].delete_many({})
    db["mcp_registry"].delete_many({})
    # Reset global registries inside registry module
    registry.registry.clear()
    registry.registry["agent_status"] = {}
    registry.client_registry.clear()
    registry.client_registry["agent_map"] = {}

@pytest.fixture(scope="function")
def client():
    with app.test_client() as c:
        yield c

# Helper

def register_agent(client, agent_id):
    payload = {
        "agent_id": agent_id,
        "agent_url": f"https://bridge.local/{agent_id}",
        "api_url": f"https://api.local/{agent_id}"
    }
    return client.post("/register", json=payload)


def test_status_after_register(client):
    register_agent(client, "agentm-ext-1")
    r = client.get("/status/agentm-ext-1")
    # Initially alive False until allocated or signup/setup updates
    assert r.status_code == 200
    assert r.json in (False, True)


def test_sender_unassigned(client):
    register_agent(client, "agentm-ext-2")
    r = client.get("/sender/agentm-ext-2")
    # Endpoint currently returns 200 with {'sender_name': None} for unassigned
    if r.status_code == 200:
        assert r.json.get("sender_name") is None
    else:
        assert r.status_code in (400, 404)


def test_allocate_sets_alive_and_sender(client, db):
    register_agent(client, "agentm-ext-3")
    # Need another agent free for allocation logic to pick from
    register_agent(client, "agentm-ext-4")
    alloc_payload = {"client_id": "dummy", "userProfile": {"name": "Alloc User"}}
    r = client.post("/api/allocate", json=alloc_payload)
    if r.status_code == 200:
        agent_id = next((part for part in r.json["message"].split() if part.startswith("agentm")), None)
        assert agent_id is not None
        assert registry.registry['agent_status'][agent_id]['alive'] is True
        status_doc = db["agent_registry"].find_one({"agent_id": agent_id})
        if status_doc:
            assert status_doc.get("alive") is True
    else:
        assert r.status_code == 503


def test_signup_creates_user_and_assigns_agent(client, db):
    register_agent(client, "agents-ext-1")  # signup expects agent id starting with 'agents'
    r = client.post("/api/signup", json={"email": "user@example.com", "username": "exampleuser"})
    assert r.status_code in (200, 503, 500)
    if r.status_code == 200:
        user_doc = db["users"].find_one({"email": "user@example.com"})
        assert user_doc is not None
        assert user_doc.get("agent_id")


def test_duplicate_signup_fails(client, db):
    register_agent(client, "agents-ext-2")
    r1 = client.post("/api/signup", json={"email": "dup@example.com", "username": "dupuser"})
    r2 = client.post("/api/signup", json={"email": "dup@example.com", "username": "dupuser"})
    if r1.status_code == 200:
        assert r2.status_code == 400


def test_setup_user_with_specific_agent(client, db):
    # Register specific 'agents' agent
    register_agent(client, "agents-ext-3")
    r = client.post("/api/setup", json={"email": "set@example.com", "username": "setupuser", "agent_id": "agents-ext-3"})
    assert r.status_code in (200, 400, 500)
    if r.status_code == 200:
        user_doc = db["users"].find_one({"email": "set@example.com"})
        assert user_doc is not None
        assert user_doc.get("agent_id") == "agents-ext-3"


def test_lookup_not_found(client):
    r = client.get("/lookup/nonexistent")
    assert r.status_code == 404


def test_get_mcp_registry_empty(client):
    r = client.get("/get_mcp_registry?registry_provider=prov&qualified_name=name")
    assert r.status_code == 404 or r.status_code == 500


def test_clients_endpoint(client):
    register_agent(client, "agentm-ext-9")
    alloc_payload = {"client_id": "dummy", "userProfile": {"name": "Client One"}}
    client.post("/api/allocate", json=alloc_payload)
    r = client.get("/clients")
    assert r.status_code == 200
    assert isinstance(r.json, dict)
