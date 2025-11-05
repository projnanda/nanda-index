# NANDA Registry with Federation

**A unified agent registry that bridges multiple agent ecosystems in real-time.**

NANDA Registry enables seamless discovery and interoperability across heterogeneous agent registries. Register agents locally, query remote registries like AGNTCY ADS, and get unified responses—all through a single API. Built with optional federation, batch synchronization, and intelligent skill taxonomy mapping.

## Features

### Core Registry
- Agent registration and management
- Client-agent allocation
- SSL certificate management
- MongoDB integration for persistence
- Automatic certificate renewal
- Extended search and status endpoints

### Batch Interoperability (`agntcy-interop/`)
- Export NANDA agents to OASF (Open Agent Schema Format)
- Import OASF records into NANDA registry
- Skill taxonomy mapping
- Batch synchronization with external registries

### Federation Layer (Optional)
- **Real-time cross-registry agent discovery**
- **`@agntcy:agent-name` routing to external registries**
- **Live queries to AGNTCY Agent Directory Service (ADS)**
- **Pluggable adapter architecture** for multiple registries
- **Automatic schema translation** (OASF ↔ NANDA)
- **Skill taxonomy integration** for semantic mapping

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│               NANDA Registry (Port 6900)                     │
│  ┌────────────────┐  ┌──────────────────────────────────┐  │
│  │  Core Registry │  │  Federation Layer (Optional)     │  │
│  │  - /register   │  │  - /federation/lookup/<id>       │  │
│  │  - /lookup     │  │  - /federation/registries        │  │
│  │  - /allocate   │  │  - Adapters: AGNTCY, local       │  │
│  └────────────────┘  └──────────────────────────────────┘  │
└────────────┬────────────────────────┬───────────────────────┘
             │                        │
      MongoDB (persist)        AGNTCY ADS (gRPC)
                                  localhost:8888
```

### Data Flow

1. **Client** sends lookup: `GET /federation/lookup/@agntcy:helper-agent`
2. **Federation Router** parses identifier: `@agntcy:helper-agent`
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

## Repository Structure

```
nanda-index-federation/
├── registry.py                    # Core registry service with federation support
├── run_registry.py                # Production launcher with SSL management
├── pyproject.toml                 # Dependency management (uv)
│
├── federation/                    # Federation layer (optional)
│   ├── adapters/
│   │   ├── base_adapter.py        # Abstract adapter interface
│   │   ├── agntcy_adapter.py      # AGNTCY ADS adapter with SkillMapper
│   │   └── registry_adapter.py    # Local NANDA registry adapter
│   ├── federation_routes.py       # Flask routes for federated lookup
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
- (Optional) `dirctl` for AGNTCY federation - see setup below

### Setting up AGNTCY ADS (Optional)

To use AGNTCY federation, you need a running AGNTCY ADS instance:

```bash
# Install dirctl (AGNTCY CLI)
brew install agntcy/tap/dirctl  # macOS
# or download from https://github.com/agntcy/agntcy

# Start ADS server
dirctl start

# Push an agent to ADS
dirctl push agent-record.json

# Verify ADS is running
dirctl status
```

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

### Starting the Registry

Basic usage:
```bash
python3 registry.py
```

With federation enabled:
```bash
export ENABLE_FEDERATION=true
export AGNTCY_ADS_URL=localhost:8888
python3 registry.py
```

Production deployment with SSL (requires root):
```bash
python3 run_registry.py --public-url https://your-domain.com --port 6900
```

## API Endpoints

### Core Endpoints
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
- `GET /stats` - Registry statistics
- `GET /mcp_servers` - List MCP servers
- `GET /skills/map?capability=<text>` - Map capability to skill taxonomy

### Federation Endpoints (when `ENABLE_FEDERATION=true`)
- `GET /federation/lookup/<agent_id>` - Federated agent lookup
  - Example: `/federation/lookup/@agntcy:helper-agent`
  - Example: `/federation/lookup/financial-analyzer` (local registry)
- `GET /federation/registries` - List all connected registries

## Environment Variables

### Core Configuration
- `MONGODB_URI`: MongoDB connection string
- `PORT`: Registry service port (default: 6900)
- `CERT_DIR`: Directory for SSL certificates (default: /root/certificates)

### Federation Configuration (Optional)
- `ENABLE_FEDERATION`: Enable federation layer (`true` or `false`, default: `false`)
- `AGNTCY_ADS_URL`: AGNTCY ADS server address (e.g., `localhost:8888`)
- `DIRCTL_PATH`: Path to dirctl binary (default: `/opt/homebrew/bin/dirctl`)
- `OASF_SCHEMA_DIR`: Path to OASF schema directory (default: auto-detect)
- `REGISTRY_URL`: Local registry URL for federation routing (default: `http://localhost:6900`)

## Security Notes

- The service requires root access for SSL certificate management
- Certificates are stored with appropriate permissions (600 for private key)
- MongoDB should be properly secured
- Use HTTPS for all communications