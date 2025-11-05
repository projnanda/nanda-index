# NANDA Registry Service

A comprehensive registry service for managing and allocating NANDA agents with federated multi-registry support. This service handles agent registration, allocation, client-agent mapping, and cross-registry agent discovery.

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

## Prerequisites

- Python 3.6+
- MongoDB
- Root/sudo access (for SSL certificate management)
- Port 80 available (for Let's Encrypt certificate challenge)
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

Preparing
apt install python3.10-venv



1. SSH into the server:
```bash
ssh root@your-server-ip
```

2. Clone the repository to /opt:
```bash
git clone https://github.com/aidecentralized/nanda-index.git /opt/nanda-index
cd /opt/nanda-index
```

3. Create and activate a virtual environment:
```bash
python3 -m venv venv && source venv/bin/activate
```

4. Install dependencies:
```bash
pip install -r requirements.txt
```

5. Set up MongoDB:
   - Install MongoDB if not already installed
   - Create a database for the registry
   - Set the MongoDB URI in environment variables:
     ```bash
     export MONGODB_URI="<provide your URI>"
     ```

## Usage

### Starting the Registry

1. Basic start with automatic SSL certificate:
```bash
python3 run_registry.py --public-url <https://your-domain.com>
```

2. Start with specific port:
```bash
python3 run_registry.py --public-url https://your-domain.com --port 6900
```


### Port Requirements

- Port 80: Required temporarily for Let's Encrypt certificate challenge
- Port 6900: Default port for the registry service
- MongoDB port: Default 27017

### SSL Certificate Management

The service automatically:
- Obtains SSL certificates from Let's Encrypt
- Stores certificates in `/root/certificates/`
- Handles certificate renewal

If port 80 is in use, the service will attempt to:
1. Identify the process using port 80
2. Stop common web servers (nginx, apache2)
3. Wait for the port to be released

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