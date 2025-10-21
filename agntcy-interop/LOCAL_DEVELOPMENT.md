# Local Development Guide (Registry & Interop)

Relocated from `nanda-index/LOCAL_DEVELOPMENT.md` to group local setup with interoperability tooling.

---

## Registry Quick Start (No SSL)
```bash
cd nanda-index
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export PORT=6900
export MONGODB_URI="mongodb://localhost:27017"  # optional if Mongo running
python registry.py
```

Start Mongo quickly (optional):
```bash
docker run -d --name mongo -p 27017:27017 mongo:6
export MONGODB_URI="mongodb://localhost:27017"
```

## Smoke Test Endpoints
```bash
curl -X POST http://localhost:6900/register \
  -H 'Content-Type: application/json' \
  -d '{"agent_id":"agentm-local-1","agent_url":"https://bridge.local/agentm-local-1","api_url":"https://api.local/agentm-local-1"}'

curl http://localhost:6900/lookup/agentm-local-1
curl http://localhost:6900/list
```

## Python Client Example
```python
from nanda_core.core.registry_client import RegistryClient
client = RegistryClient(registry_url="http://localhost:6900")
print(client.list_agents())
print(client.lookup_agent("agentm-local-1"))
```

## Interoperability Scripts
- Export: `agntcy-interop/export_nanda_to_agntcy.py`
- Sync (import): `agntcy-interop/sync_agntcy_dir.py`

Use `--dry-run` for safe previews. Wrapper scripts at root provide backward compatibility.

## Tips
- Disable SSL verification only for development.
- Keep agent IDs consistent (`agentm-*`).
- Register several agents before allocation tests.

## Planned Enhancements
- .env loading
- Docker Compose (registry + Mongo + sample agents)
- Health and search endpoints parity with client expectations

---
Maintained with interoperability documentation.