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

### Interoperability

- **Batch Operations** (`agntcy-interop/`) - Export/import OASF records, skill taxonomy mapping, batch sync
- **Switchboard** (`switchboard/`) - Real-time cross-registry discovery including AGNTCY ADS integration

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

## Repository Structure

```
nanda-index/
├── registry.py                    # Core index service
├── run_registry.py                # Production launcher with SSL management
├── pyproject.toml                 # Dependency management (uv)
│
├── switchboard/                   # Cross-registry discovery (see switchboard/README.md)
│   ├── adapters/                  # Registry adapters (AGNTCY, local)
│   ├── switchboard_routes.py      # Routing logic
│   └── tests/                     # Integration tests
│
└── agntcy-interop/                # Batch interoperability tools
    ├── batch/                     # Export/import scripts
    ├── adapters/                  # Schema adapters
    ├── docs/                      # Interop documentation
    └── tests/                     # Batch operation tests
```

## Prerequisites

- Python 3.6+
- MongoDB

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

## Environment Variables

### Core Configuration
- `MONGODB_URI`: MongoDB connection string
- `PORT`: Index service port (default: 6900)
- `CERT_DIR`: Directory for SSL certificates (default: /root/certificates)

## Interoperability

NANDA Index supports interoperability with external agent registries:

### Batch Operations
See `agntcy-interop/` for OASF export/import tools and skill taxonomy mapping.

### Switchboard (Cross-Registry Discovery)
See [`switchboard/README.md`](switchboard/README.md) for AGNTCY ADS integration and live agent lookup across registries.

**Enable with:**
```bash
export ENABLE_FEDERATION=true
export AGNTCY_ADS_URL=localhost:8888
python3 registry.py
```

When enabled, adds endpoints:
- `GET /switchboard/lookup/<agent_id>` - Cross-registry agent lookup
- `GET /switchboard/registries` - List connected registries

## Security Notes

- MongoDB should be properly secured with authentication
- Use HTTPS for production deployments
- Certificates are stored with appropriate permissions (600 for private key)
- The service requires root access for SSL certificate management