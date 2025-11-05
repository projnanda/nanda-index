# AgentFacts / OASF Interoperability Guide

This document consolidates taxonomy integration details and the planned end‑to‑end flow between the Nanda Index registry and AGNTCY (OASF / AgentFacts) artifacts.

## Goals
1. Export Nanda agents as valid AgentFacts (OASF) `record` JSON documents.
2. Import AgentFacts records back into the registry with validation and minimal loss.
3. Provide on‑demand capability → skill mapping for enrichment (`/skills/map`).
4. Maintain version and schema compatibility safeguards.

## Components
| Component | File / Endpoint | Purpose |
|-----------|-----------------|---------|
| Registry Service | `registry.py` | Core agent CRUD, search, status update, allocation, skill mapping endpoint. |
| Export Script | `export_nanda_to_agntcy.py` | Converts registry agents → OASF record JSON. |
| Import Script (planned) | `sync_agntcy_dir.py` (future rename) | Ingest OASF record files → registry agents. |
| Skill Mapper | in exporter + embedded in `/skills/map` | Resolves free‑form capabilities → structured skill objects. |
| Adapter Module (planned) | `agentfacts_adapter.py` | Normalizes & validates AgentFacts documents pre‑import/export. |
| Validation Schema | `../agntcy/oasf/schema` | Source of taxonomies (skills/categories) & JSON Schemas. |

## Capability → Skill Mapping
The mapping pipeline transforms a free‑form capability string into a skill payload:

### Resolution Order
1. Exact name match against leaf skills (`name` normalized: lowercase, spaces & hyphens → underscores).
2. Caption substring match (`caption` field of leaf).
3. Heuristic rules (e.g. `chat` → `natural_language_generation`, `tool` → `tool_use_planning`).
4. Parent skill inference (attempt mapping against non‑leaf parent names).

### Returned Payload Example
```json
{
  "skill_id": "text_classification",
  "category_name": "Natural Language Processing",
  "category_uid": 1,
  "class_name": "Text Classification",
  "class_uid": 9
}
```

### De‑duplication
During export, multiple capabilities that map to the same `skill_id` are collapsed to one entry.

### Endpoint Usage
`GET /skills/map?capability=<string>` returns either structured mapping or a `404` when not found; initialization errors produce `500` with diagnostics.

## Export Workflow
1. Enumerate agents via `/list` or targeted ID(s).
2. For each agent build the record:
   - `name` + `version` from `agent_id` (split on last `:`; default version `v0`).
   - `locators`: bridge URL + API URL.
   - `skills`: mapped via Skill Mapper if schema available.
   - `extensions`: MCP runtime extension if `api_url` is `cmd://...` form.
   - `description`: concatenated capabilities + tags.
3. Write `<name>.record.json`.

## Import Workflow (Planned)
1. Read each `*.record.json`.
2. Validate against AgentFacts / OASF JSON Schema.
3. Extract:
   - `agent_id` ← `name:version` (sanitize `/` → `-`).
   - `agent_url` ← first locator (pref `docker-image`, else fallback placeholder).
   - `api_url` ← runtime MCP extension command encoded to `cmd://` form.
   - (Optional) derive `capabilities` from `skills` list (exact skill_ids or captions).
   - (Optional) derive `tags` from categories / modules.
4. Register via `/register` then update status using `/agents/<id>/status` for capabilities/tags.

## Planned Adapter (`agentfacts_adapter.py`)
Responsibilities:
- Load and cache JSON Schemas (record + modules + skill taxonomy).
- Provide `validate_record(record: dict) -> (bool, errors)`.
- Extract / normalize fields for registry insertion.
- Round‑trip consistency check (`registry_agent -> record -> agent_draft`).
- Version guard: reject if record schema version not in supported set.

### Adapter Contract Sketch
```python
class AgentFactsAdapter:
    def __init__(self, schema_root: Path, supported_versions: list[str]):
        ...
    def validate_record(self, record: dict) -> tuple[bool, list[str]]: ...
    def record_to_registry(self, record: dict) -> dict: ...  # returns agent registration payload
    def registry_to_record(self, agent: dict, mapper: SkillMapper | None) -> dict: ...
```

## Versioning Guard
Records should include either `$id` or a top‑level `schema_version` field. The adapter will:
1. Parse version (e.g. `v1.0.0`).
2. Ensure it is within `supported_versions`.
3. Reject unsupported with actionable error (`{"error": "unsupported_schema_version", "found": "v0.8.0"}`).

## Testing Strategy
| Test Type | Purpose |
|-----------|---------|
| Unit (SkillMapper) | Exact, substring, heuristic, parent, de‑dup. |
| Endpoint (`/skills/map`) | Initialization / mapping / error codes. |
| Export Integration | Generated record correctness (locators, extensions, skills). |
| Import Validation | Invalid schema, missing required fields. |
| Round‑Trip | Export → import → export equality on stable subset. |
| Version Guard | Supported vs unsupported schema versions. |

## Edge Cases & Considerations
| Case | Handling |
|------|----------|
| Missing taxonomy files | Skip mapping; log warning; endpoint returns 500 or 404. |
| Capability maps to non‑leaf | Resolve to first leaf child when possible. |
| Duplicate capabilities | De‑dup skill list. |
| Unsupported schema version | Reject import. |
| Partial record (missing locators) | Fallback `placeholder://<agent_id>` for bridge locator. |

## CLI & API Extensions (Planned)
| Command | Description |
|---------|-------------|
| `--import-agentfacts <dir>` | Bulk import validated records. |
| `--export-agentfacts` | Alias for existing export script with added adapter options. |
| `/agentfacts/import` (POST) | Upload/validate a single record JSON; auto-register. |
| `/agentfacts/validate` (POST) | Return validation diagnostics without registering. |

## Roadmap
1. Implement `AgentFactsAdapter` with schema loading & validation.
2. Add import endpoints & CLI flags.
3. Version guard enforcement.
4. Round‑trip test suite.
5. Enhanced capability inference from skills (reverse mapping using taxonomy parents).

## Troubleshooting
| Symptom | Resolution |
|---------|------------|
| `/skills/map` 500 (mapper_init_failed) | Verify `OASF_SCHEMA_DIR` path and taxonomy presence. |
| Export produces empty `skills` | Check capabilities names vs taxonomy; consider adding custom mapping file. |
| Import rejects record | Run adapter validate endpoint to see error list. |
| Duplicate agents after import | Use prefix filtering or implement uniqueness check by hash (planned). |

---
Maintained with interoperability tooling under `agntcy-interop/`.