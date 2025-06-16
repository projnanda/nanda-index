# NANDA Registry Service

A registry service for managing and allocating NANDA agents. This service handles agent registration, allocation, and client-agent mapping.

## Features

- Agent registration and management
- Client-agent allocation
- SSL certificate management
- MongoDB integration for persistence
- Automatic certificate renewal

## Prerequisites

- Python 3.6+
- MongoDB
- Root/sudo access (for SSL certificate management)
- Port 80 available (for Let's Encrypt certificate challenge)

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

- `/register` - Register a new agent
- `/lookup/<id>` - Lookup agent by ID
- `/api/allocate` - Allocate an agent to a client
- `/list` - List all registered agents
- `/status/<agent_id>` - Get agent status
- `/clients` - List all clients

## Environment Variables

- `MONGODB_URI`: MongoDB connection string

Optional
- `PORT`: Registry service port (default: 6900)
- `CERT_DIR`: Directory for SSL certificates (default: /root/certificates)

## Troubleshooting

### Port 80 Issues

If you see port 80 is in use:
1. Check what's using port 80:
```bash
sudo lsof -i :80
```

2. Stop the service:
```bash
sudo systemctl stop nginx  # if nginx is running
sudo systemctl stop apache2  # if apache is running
```

3. Verify port is free:
```bash
sudo netstat -tulpn | grep :80
```

### Certificate Issues

If SSL certificate setup fails:
1. Check if the domain is publicly accessible
2. Ensure port 80 is available
3. Verify DNS is properly configured
4. Check certificate directory permissions

## Security Notes

- The service requires root access for SSL certificate management
- Certificates are stored with appropriate permissions (600 for private key)
- MongoDB should be properly secured
- Use HTTPS for all communications

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

[Add your license information here] 