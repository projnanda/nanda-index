# Exporting Nanda Registry Agents to AGNTCY OASF Records

Moved here from repository root for organization. Original path: `nanda-index/EXPORT_TO_AGNTCY_DIR.md`.

_Use either the backward compatibility wrapper `export_nanda_to_agntcy.py` at repo root or invoke directly: `python agntcy-interop/export_nanda_to_agntcy.py`._

---

## Original Guide

This guide describes how to generate OASF-compatible `*.record.json` files from agents registered in the Nanda Index.

### Script
`export_nanda_to_agntcy.py`

### Mapping Summary
| Nanda Field | OASF Field | Notes |
|-------------|-----------|-------|
| agent_id | name + version | Split on last ':'; if missing version -> v0 |
| agent_url | locators[type=bridge-url] | Primary locator |
| api_url | locators[type=api-url] | Optional second locator |
| last_update | created_at | Fallback to current UTC if absent |
| capabilities | skills | Mapped via heuristic using OASF schema (see below) |
| tags | description | Appended as plain text |
| api_url cmd:// form | MCP extension | Creates runtime/mcp extension with command/args |

### Usage Examples
Export all agents:
```
python nanda-index/export_nanda_to_agntcy.py --registry-url http://localhost:6900
```
Dry run:
```
python nanda-index/export_nanda_to_agntcy.py --dry-run
```
Only one agent:
```
python nanda-index/export_nanda_to_agntcy.py --agent-id agentm-foo:v1
```
Filter by prefix:
```
python nanda-index/export_nanda_to_agntcy.py --agent-prefix agentm-
```
Limit output:
```
python nanda-index/export_nanda_to_agntcy.py --limit 5
```
Custom output directory:
```
python nanda-index/export_nanda_to_agntcy.py --out-dir ./oasf-out
```

### Output
Files are written as `<name>.record.json` in the chosen output directory.

### MCP Extension Generation
If the agent's `api_url` is a synthesized `cmd://` URL (produced during AGNTCY import sync), the script emits a runtime MCP extension stub:
```json
{
	"name": "schema.oasf.agntcy.org/features/runtime/mcp",
	"version": "v1.0.0",
	"data": { "servers": { "nanda-export": { "command": "docker", "args": ["run", "image"], "env": {} } } }
}
```

### Limitations / Future Work
1. Capability mapping heuristic may be imprecise; consider adding explicit mapping config.
2. Tags not mapped to domains/modules.
3. No digest calculation or signature enrichment.
4. Duplicate exports overwrite silently.
5. No differential update logic (always writes file).
6. Skills list may contain duplicates if multiple capabilities resolve to same leaf skill (future: de-dup).

### Capability → Skill Mapping
The export script attempts to convert free-form `capabilities` into OASF skills using the schema at `--oasf-schema-dir`:
Heuristic order:
1. Exact match to leaf skill `name` (normalized: lowercase, spaces/hyphens → underscores).
2. Substring match within leaf skill caption.
3. Fallback rules:
	 - chat, conversation → natural_language_generation
	 - classif → text_classification
	 - retriev, search → information_retrieval_synthesis
	 - vision, image → (placeholder: text_classification until vision leaf loaded)

Each mapped skill becomes an object:
```
{
	"category_name": "Natural Language Processing",
	"category_uid": 1,
	"class_name": "Text Classification",
	"class_uid": 9
}
```
To disable mapping, omit the schema directory or point `--oasf-schema-dir` to a non-existing path.


### Suggested Enhancements
- Pull skills/domain dictionaries from OASF schema and map heuristically.
- Allow status-based filtering (alive only) via a flag.
- Inject authors from a supplemental mapping file.
- Generate a manifest of exported agents for downstream automation.

### Related Scripts
- `sync_agntcy_dir.py`: Imports AGNTCY OASF records into Nanda.

Together these provide a bi-directional (though lossy) sync path.