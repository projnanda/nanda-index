# Skills Taxonomies for NANDA Index

This directory contains skill classification taxonomies for different domains, enabling semantic agent discovery via the `/skills/map` endpoint.

## Space Industry Taxonomy

**File:** `space_skills_taxonomy.json`

Hierarchical skill classification for space industry AI agents including:
- Space Regulatory Compliance (FCC, FAA, ITU, NOAA, ITAR)
- Satellite Operations
- Spectrum Management
- Mission Planning
- Ground Systems
- Space Insurance & Finance

**Contributor:** Astrocity Foundation - Space Industry Standards Initiative
**License:** MIT
**Regulatory Basis:** Based on publicly documented US space regulations

## Usage

Agents register with relevant skill IDs from these taxonomies to enable capability-based discovery.

Example agent registration:
```json
{
  "agent_id": "fcc-compliance-agent-001",
  "capabilities": [
    "fcc_satellite_licensing",
    "orbital_debris_assessment"
  ]
}
```

Discovery query:
```
GET /skills/map?query=fcc+satellite+licensing
```
