# Syncing AGNTCY Directory Records into Nanda Index

Moved here from `nanda-index/SYNC_AGNTCY_DIR.md`.

This explains how to import AGNTCY `*.record.json` files (OASF agent records) into the Nanda Index registry.

---

## Original Guide

Each AGNTCY record is converted into a minimal Nanda agent registration:
- `agent_id`: `{name}:{version}` with `/` replaced by `-`
- `agent_url`: First locator URL (prefers `docker-image`), else placeholder.
- `api_url`: From MCP runtime extension command encoded as `cmd://command?args=...`.

Script location: `agntcy-interop/sync_agntcy_dir.py` (invocation via root wrapper TBD).

### Usage
```
python agntcy-interop/sync_agntcy_dir.py --records-path ../agntcy/dir/docs/research/integrations --registry-url http://localhost:6900
```
Dry run:
```
python agntcy-interop/sync_agntcy_dir.py --records-path ../agntcy/dir/docs/research/integrations --dry-run
```
Limit processed files:
```
python agntcy-interop/sync_agntcy_dir.py --limit 5 --records-path ../agntcy/dir/docs/research/integrations
```

### Field Mapping
| OASF Field | Nanda Registry Field | Notes |
|------------|----------------------|-------|
| name + version | agent_id | Combined, `/` -> `-` |
| First locator | agent_url | Prefers docker-image; fallback placeholder |
| MCP extension server command | api_url | Encoded `cmd://` form |
| (future) skills | capabilities | Future enhancement |

### Planned Improvements
- Derive capabilities from skills
- Tag inference from categories
- Health probing and status update
- Incremental updates (hash compare)

### Exit Codes
- 0 success (>=1 registration or dry run ok)
- 1 no registrations
- 2 invalid records path

---
Maintained as part of interoperability between AGNTCY and Nanda.