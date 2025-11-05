# AGNTCY / AgentFacts Interoperability

This directory contains interoperability tooling between the Nanda Index registry and the AGNTCY (OASF / AgentFacts) ecosystem.

## Contents
- `export_nanda_to_agntcy.py` – Export registered agents to OASF-compatible `*.record.json` files.
- (future) `import_agentfacts.py` – Import AgentFacts JSON into the registry.
- (future) `agentfacts_adapter.py` – Validation & mapping helpers for AgentFacts schema.

## Skill Taxonomy Mapping
The exporter loads the OASF skill taxonomy (categories + skills) from the path provided by `--oasf-schema-dir` (default: `../agntcy/oasf/schema`). It maps free‐form capability strings to structured skill objects using:
1. Exact skill name match.
2. Caption substring match.
3. Heuristic fallbacks (chat → natural_language_generation, tool → tool_use_planning, etc.).
4. Category resolution via parent `extends` chain.

Duplicate mappings are de‑duplicated by `skill_id`.

## Usage
```bash
python agntcy-interop/export_nanda_to_agntcy.py --registry-url http://localhost:6900 --out-dir ./oasf-out
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
