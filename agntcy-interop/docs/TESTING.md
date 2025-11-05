# Testing the NANDA Registry Service

Basic pytest tests are provided under `tests/`.

## Install Test Dependencies

```bash
pip install -r requirements.txt
pip install pytest
```

## Run Tests

```bash
pytest -q
```

## What Is Covered

- Agent registration & lookup
- Allocation logic (tolerates 503 when no available agents)
- Listing agents & clients

## Extending Tests

Recommended future additions:

1. MongoDB persistence (start ephemeral MongoDB before tests)
2. Validation of error responses for malformed payloads
3. Concurrency tests (multiple `/api/allocate` calls in parallel)
4. Endpoint coverage for signup/setup flows
5. MCP registry retrieval behavior (`/get_mcp_registry`)

## Example: Adding a MongoDB Test (Placeholder)

```python
# tests/test_mongo_persistence.py (example sketch)
import os
from registry import app
from pymongo import MongoClient

def test_persistence_roundtrip(tmp_path):
    os.environ['MONGODB_URI'] = 'mongodb://localhost:27017'
    client = MongoClient(os.environ['MONGODB_URI'])
    db = client['iot_agents_db']
    with app.test_client() as c:
        payload = {"agent_id":"agentm-mongo-1","agent_url":"https://bridge/agentm-mongo-1","api_url":"https://api/agentm-mongo-1"}
        r = c.post('/register', json=payload)
        assert r.status_code == 200
        # Ensure document exists
        doc = db['agent_registry'].find_one({"agent_id":"agentm-mongo-1"})
        assert doc is not None
```

## Coverage Targets (Suggested)

- 80% statements for core CRUD endpoints
- 100% for helper functions `save_registry` / `save_client_registry`

## Performance Considerations

When scaling tests:
- Use fixtures to reuse test clients
- Consider a test MongoDB database name like `iot_agents_test_db`
- Clean collections between tests to isolate state
