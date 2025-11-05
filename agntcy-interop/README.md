# AGNTCY / AgentFacts Interoperability

This directory contains interoperability tooling between the Nanda Index registry and the AGNTCY (OASF / AgentFacts) ecosystem.

## Directory Structure

```
agntcy-interop/
├── batch/                          # Batch synchronization scripts
│   ├── export_nanda_to_agntcy.py  # Export NANDA → OASF files
│   └── sync_agntcy_dir.py         # Import OASF files → NANDA
├── adapters/                       # Schema adapters
│   └── agentfacts_adapter.py      # Validation & conversion
├── docs/                           # Documentation
├── tests/                          # Test suite
└── scripts/                        # Helper scripts
```

## Skill Taxonomy Mapping
The exporter loads the OASF skill taxonomy (categories + skills) from the path provided by `--oasf-schema-dir` (default: `../agntcy/oasf/schema`). It maps free‐form capability strings to structured skill objects using:
1. Exact skill name match.
2. Caption substring match.
3. Heuristic fallbacks (chat → natural_language_generation, tool → tool_use_planning, etc.).
4. Category resolution via parent `extends` chain.

Duplicate mappings are de‑duplicated by `skill_id`.

## Usage

### Export NANDA to OASF
```bash
python agntcy-interop/batch/export_nanda_to_agntcy.py --registry-url http://localhost:6900 --out-dir ./oasf-out
```

### Import OASF to NANDA
```bash
python agntcy-interop/batch/sync_agntcy_dir.py --records-path ./oasf-records --registry-url http://localhost:6900
```
Additional flags:
- `--agent-id <id>` – export a single agent.
- `--agent-prefix <prefix>` – filter agent IDs.
- `--dry-run` – print JSON without writing files.
- `--oasf-schema-dir <path>` – override schema path.
- `--limit N` – limit number of exported agents.

## Planned Additions
- Importer with AgentFacts JSON Schema validation.
- Round‐trip tests (import → registry → export consistency).
- Version guard (`$id` / schema version) checks.
- CLI & API endpoints for import/export.

## Environment Variables
- `REGISTRY_URL` – default registry base URL.
- `OASF_SCHEMA_DIR` – default path to OASF schema root.

## License
See repository root license.
