# NANDA Index

**A unified agent index for discovery and interoperability across agent ecosystems.**

NANDA Index provides a centralized registry for AI agents with capabilities-based search, MongoDB persistence, and optional cross-registry discovery. Register agents locally, search by skills and metadata, and optionally bridge to external registries like AGNTCY ADS—all through a single API.

## Features

### Core Index
- **Agent registration and management** - Register agents with capabilities, metadata, and endpoints
- **Capabilities-based search** - Query agents by skills, tags, and attributes
- **MongoDB persistence** - Durable storage with flexible schema
- **Client-agent allocation** - Automatic assignment and tracking
- **Extended API** - Rich endpoints for search, stats, and management
- **SSL support** - Production-ready deployment with automatic certificate management

### Batch Interoperability (`agntcy-interop/`)
- **Export to OASF** - Convert NANDA agents to OASF (Open Agent Schema Format)
- **Import from OASF** - Bulk import OASF records into NANDA Index
- **Skill taxonomy mapping** - Intelligent capability translation using AGNTCY taxonomy
- **Batch synchronization** - Bulk sync operations with external registries

### Switchboard
- **AGNTCY ADS interoperability** - Real-time queries to AGNTCY Agent Directory Service
- **Cross-index routing** - `@agntcy:agent-name` identifier support
- **Automatic schema translation** - OASF ↔ NANDA AgentFacts conversion
- **Pluggable adapter architecture** - Extensible for multiple registries

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                 NANDA Index (Port 6900)                      │
│  ┌────────────────┐  ┌──────────────────────────────────┐  │
│  │  Core Index    │  │  Switchboard                     │  │
│  │  - /register   │  │  - /federation/lookup/<id>       │  │
│  │  - /lookup     │  │  - /federation/registries        │  │
│  │  - /search     │  │  - Adapters: AGNTCY, local       │  │
│  │  - /allocate   │  │                                  │  │
│  └────────────────┘  └──────────────────────────────────┘  │
└────────────┬────────────────────────┬───────────────────────┘
             │                        │
      MongoDB (persist)        AGNTCY ADS (gRPC)
                                  localhost:8888
```

## Repository Structure

```
nanda-index/
├── registry.py                    # Core index service with switchboard support
├── run_registry.py                # Production launcher with SSL management
├── pyproject.toml                 # Dependency management (uv)
│
├── federation/                    # Switchboard (optional)
│   ├── adapters/
│   │   ├── base_adapter.py        # Abstract adapter interface
│   │   ├── agntcy_adapter.py      # AGNTCY ADS adapter with SkillMapper
│   │   └── registry_adapter.py    # Local NANDA index adapter
│   ├── federation_routes.py       # Flask routes for cross-registry lookup
│   └── tests/
│       ├── test_integration.py    # Unit-level integration tests
│       ├── test_end_to_end.py     # E2E tests with real servers
│       └── utils/
│           └── *.json             # OASF agent fixtures for testing
│
└── agntcy-interop/                # Batch interoperability tools
    ├── batch/
    │   ├── export_nanda_to_agntcy.py   # Export with SkillMapper
    │   └── sync_agntcy_dir.py          # Bulk sync operations
    ├── adapters/
    │   └── agentfacts_adapter.py       # AgentFacts schema adapter
    ├── docs/                           # Interop documentation
    └── tests/                          # Batch operation tests
```

## Prerequisites

- Python 3.6+
- MongoDB
- (Optional) `dirctl` for AGNTCY ADS interop - see Switchboard section

## Installation

1. Clone the repository:
```bash
git clone https://github.com/projnanda/nanda-index.git
cd nanda-index
```

2. Install dependencies using `uv`:
```bash
uv sync
```

3. Set up MongoDB and configure environment:
```bash
export MONGODB_URI="mongodb://localhost:27017/nanda"
```

## Usage

### Starting the Index

Basic usage:
```bash
python3 registry.py
```

Production deployment with SSL (requires root):
```bash
python3 run_registry.py --public-url https://your-domain.com --port 6900
```

## API Endpoints

### Core Index Endpoints
- `POST /register` - Register a new agent
- `GET /lookup/<id>` - Lookup agent by ID
- `POST /api/allocate` - Allocate an agent to a client
- `GET /list` - List all registered agents
- `GET /status/<agent_id>` - Get agent status
- `GET /clients` - List all clients

### Extended Endpoints
- `GET /search` - Search agents by query, capabilities, tags
- `GET /agents/<agent_id>` - Get detailed agent information
- `DELETE /agents/<agent_id>` - Remove an agent
- `PUT /agents/<agent_id>/status` - Update agent status
- `GET /health` - Health check
- `GET /stats` - Index statistics
- `GET /mcp_servers` - List MCP servers
- `GET /skills/map?capability=<text>` - Map capability to skill taxonomy

### Switchboard Endpoints (when `ENABLE_FEDERATION=true`)
- `GET /federation/lookup/<agent_id>` - Cross-registry agent lookup
  - Example: `/federation/lookup/@agntcy:helper-agent`
  - Example: `/federation/lookup/financial-analyzer` (local index)
- `GET /federation/registries` - List all connected registries

## Environment Variables

### Core Configuration
- `MONGODB_URI`: MongoDB connection string
- `PORT`: Index service port (default: 6900)
- `CERT_DIR`: Directory for SSL certificates (default: /root/certificates)

### Switchboard Configuration (Optional)
- `ENABLE_FEDERATION`: Enable switchboard (`true` or `false`, default: `false`)
- `AGNTCY_ADS_URL`: AGNTCY ADS server address (e.g., `localhost:8888`)
- `DIRCTL_PATH`: Path to dirctl binary (default: `/opt/homebrew/bin/dirctl`)
- `OASF_SCHEMA_DIR`: Path to OASF schema directory (default: auto-detect)
- `REGISTRY_URL`: Local index URL for routing (default: `http://localhost:6900`)

## Switchboard: AGNTCY ADS Interoperability

The optional Switchboard enables real-time queries to external registries like AGNTCY ADS, with automatic schema translation between OASF and NANDA formats.

### Setup

Install dirctl (AGNTCY CLI):

```bash
# Install dirctl
brew install agntcy/tap/dirctl  # macOS
# or download from https://github.com/agntcy/agntcy

# Start ADS server
dirctl start

# Push an agent to ADS
dirctl push agent-record.json

# Verify ADS is running
dirctl status
```

### Enabling Switchboard

```bash
export ENABLE_FEDERATION=true
export AGNTCY_ADS_URL=localhost:8888
python3 registry.py
```

### Cross-Registry Lookup

Query AGNTCY agent:
```bash
curl http://localhost:6900/federation/lookup/@agntcy:helper-agent
```

Query local NANDA agent:
```bash
curl http://localhost:6900/federation/lookup/financial-analyzer
```

List connected registries:
```bash
curl http://localhost:6900/federation/registries
```

### Data Flow

1. **Client** sends lookup: `GET /federation/lookup/@agntcy:helper-agent`
2. **Switchboard Router** parses identifier: `@agntcy:helper-agent`
3. **AGNTCY Adapter**:
   - Queries ADS via gRPC SDK
   - Retrieves OASF record
   - Maps skills using taxonomy
   - Translates to NANDA format
4. **Response**: Unified NANDA AgentFacts JSON

### Schema Translation Example

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

**Field Mapping (OASF → NANDA):**
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

**SkillMapper enrichment:** When taxonomy is available, hierarchical OASF skill paths like `images_computer_vision/image_segmentation` are mapped to structured capability objects with category metadata, UIDs, and human-readable names.

## Security Notes

- MongoDB should be properly secured with authentication
- Use HTTPS for production deployments
- Certificates are stored with appropriate permissions (600 for private key)
- The service requires root access for SSL certificate management