# Switchboard: Cross-Registry Agent Discovery

**Real-time agent discovery across multiple registries with automatic schema translation.**

Switchboard enables NANDA Index to query external agent registries (like AGNTCY ADS) in real-time, automatically translating between different schema formats while maintaining a unified API.

Enable by setting `ENABLE_FEDERATION=true` and configuring registry endpoints (see Setup section).

## Features

- **AGNTCY ADS Integration** - Query agents from AGNTCY Agent Directory Service via gRPC
- **Cross-registry routing** - Use `@agntcy:agent-name` to specify external registries
- **Automatic schema translation** - OASF ↔ NANDA AgentFacts conversion
- **Skill taxonomy mapping** - Intelligent capability translation using AGNTCY taxonomy
- **Pluggable adapter architecture** - Easily extend to support additional registries

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                 NANDA Index (Port 6900)                      │
│  ┌────────────────┐  ┌──────────────────────────────────┐  │
│  │  Core Index    │  │  Switchboard                     │  │
│  │  - /register   │  │  - /switchboard/lookup/<id>      │  │
│  │  - /lookup     │  │  - /switchboard/registries       │  │
│  │  - /search     │  │  - Adapters: AGNTCY, local       │  │
│  │  - /allocate   │  │  (enable via ENABLE_FEDERATION)  │  │
│  └────────────────┘  └──────────────────────────────────┘  │
└────────────┬────────────────────────┬───────────────────────┘
             │                        │
      MongoDB (persist)        AGNTCY ADS (gRPC)
                                  localhost:8888
```

## Prerequisites

- NANDA Index installed (see main README)
- `dirctl` - AGNTCY CLI tool for ADS interaction
- Running AGNTCY ADS instance (local or remote)

## Setup

### 1. Install dirctl

```bash
# macOS
brew install agntcy/tap/dirctl

# Or download from https://github.com/agntcy/agntcy
```

### 2. Start AGNTCY ADS

```bash
# Start local ADS server
dirctl start

# Verify it's running
dirctl status

# (Optional) Push a test agent
dirctl push agent-record.json
```

### 3. Enable Switchboard

Set environment variables and start the index:

```bash
export ENABLE_FEDERATION=true
export AGNTCY_ADS_URL=localhost:8888
python3 registry.py
```

## Usage

### API Endpoints

When Switchboard is enabled, the following endpoints become available:

#### Cross-Registry Lookup
```
GET /switchboard/lookup/<agent_id>
```

Query AGNTCY agent:
```bash
curl http://localhost:6900/switchboard/lookup/@agntcy:helper-agent
```

Query local NANDA agent:
```bash
curl http://localhost:6900/switchboard/lookup/financial-analyzer
```

#### List Connected Registries
```
GET /switchboard/registries
```

```bash
curl http://localhost:6900/switchboard/registries
```

Response:
```json
{
  "registries": [
    {"registry_id": "nanda", "status": "active"},
    {"registry_id": "agntcy", "status": "active"}
  ],
  "count": 2
}
```

## Configuration

### Environment Variables

- **`ENABLE_FEDERATION`** - Enable switchboard (`true` or `false`, default: `false`)
- **`AGNTCY_ADS_URL`** - AGNTCY ADS server address (e.g., `localhost:8888`)
- **`DIRCTL_PATH`** - Path to dirctl binary (default: `/opt/homebrew/bin/dirctl`)
- **`OASF_SCHEMA_DIR`** - Path to OASF schema directory (default: auto-detect)
- **`REGISTRY_URL`** - Local index URL for routing (default: `http://localhost:6900`)

## How It Works

### Data Flow

1. **Client** sends lookup: `GET /switchboard/lookup/@agntcy:helper-agent`
2. **Switchboard Router** parses identifier: `@agntcy:helper-agent`
3. **AGNTCY Adapter**:
   - Queries ADS via gRPC SDK
   - Retrieves OASF record
   - Maps skills using taxonomy
   - Translates to NANDA format
4. **Response**: Unified NANDA AgentFacts JSON

### Schema Translation

The Switchboard automatically translates between OASF (AGNTCY) and NANDA AgentFacts formats.

**Original OASF Agent (from AGNTCY ADS):**
```json
{
  "name": "vision-agent",
  "version": "v1.0.0",
  "description": "Computer vision agent for image analysis",
  "schema_version": "0.7.0",
  "skills": [
    {
      "id": 201,
      "name": "images_computer_vision/image_segmentation"
    }
  ],
  "authors": ["NANDA Team"],
  "created_at": "2025-11-05T00:00:00Z",
  "locators": [
    {
      "type": "source_code",
      "url": "https://github.com/nanda/vision-agent"
    }
  ]
}
```

**Translated NANDA AgentFacts:**
```json
{
  "agent_id": "@agntcy:vision-agent",
  "registry_id": "agntcy",
  "agent_name": "vision-agent",
  "version": "v1.0.0",
  "description": "Computer vision agent for image analysis",
  "capabilities": [
    {
      "skill_id": "image_segmentation",
      "category_name": "Images & Computer Vision",
      "category_uid": 200,
      "class_name": "Image Segmentation",
      "class_uid": 201
    }
  ],
  "agent_url": "https://github.com/nanda/vision-agent",
  "api_url": "",
  "last_updated": "2025-11-05T00:00:00Z",
  "schema_version": "nanda-v1",
  "source_schema": "oasf",
  "oasf_schema_version": "0.7.0"
}
```

### Field Mapping (OASF → NANDA)

```
name                  → agent_name
version               → version
description           → description
skills[].name         → capabilities[] (via SkillMapper taxonomy)
locators[source_code] → agent_url
locators[api]         → api_url
created_at            → last_updated
schema_version        → oasf_schema_version

Generated fields:
  agent_id: "@{registry_id}:{name}"
  registry_id: "agntcy"
  schema_version: "nanda-v1"
  source_schema: "oasf"
```

### SkillMapper Integration

When the AGNTCY taxonomy is available, hierarchical OASF skill paths like `images_computer_vision/image_segmentation` are automatically mapped to structured capability objects with:

- Full taxonomy metadata
- Category names and UIDs
- Human-readable class names
- Hierarchical skill relationships

Without taxonomy, skills are extracted as simple string identifiers.

## Architecture Details

### Adapter Pattern

The Switchboard uses a pluggable adapter architecture:

```
switchboard/
├── adapters/
│   ├── base_adapter.py        # Abstract adapter interface
│   ├── agntcy_adapter.py      # AGNTCY ADS adapter
│   └── registry_adapter.py    # Local NANDA index adapter
└── switchboard_routes.py      # Flask routing logic
```

**BaseRegistryAdapter** - Abstract interface that all adapters implement:
- `query_agent()` - Query the native registry
- `translate_to_nanda()` - Translate to NANDA format
- `lookup()` - Combined query + translation
- `get_registry_info()` - Registry metadata

**AGNTCYAdapter** - Connects to AGNTCY ADS via gRPC SDK:
- Uses `agntcy-dir-sdk` for ADS communication
- Integrates `SkillMapper` for taxonomy mapping
- Handles OASF → NANDA translation

**RegistryAdapter** - Queries the local NANDA index:
- Queries local `/agents/<id>` or `/lookup/<id>` endpoints
- Returns data already in NANDA format

### Adding New Adapters

To support additional registries:

1. Create a new adapter in `adapters/` extending `BaseRegistryAdapter`
2. Implement `query_agent()` and `translate_to_nanda()`
3. Register the adapter in `SwitchboardRouter._init_adapters()`
4. Add registry identifier prefix (e.g., `@newregistry:agent-name`)

## Testing

Run integration tests:

```bash
cd switchboard/tests
python3 test_integration.py
```

Run end-to-end tests (requires running ADS):

```bash
# Start local ADS
dirctl start

# Run E2E tests
python3 test_end_to_end.py
```

Test fixtures are available in `tests/utils/` for OASF agent records.

## Related Documentation

- [AGNTCY Interoperability](../agntcy-interop/docs/) - Batch import/export tools
- [AGNTCY Documentation](https://docs.agntcy.org/) - Official AGNTCY docs
- [OASF Schema](https://github.com/agntcy/oasf) - Open Agent Schema Format

