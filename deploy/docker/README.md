# Nanda index docker-compose deployment

This document describes how to deploy the **Nanda Index** along with **MongoDB** using Docker Compose.

---

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) ≥ 24.0  
- [Docker Compose](https://docs.docker.com/compose/install/) ≥ 2.0  
- Optional: SSL certificates for HTTPS

---

## Deployment Steps

### 1. Navigate to the Docker Compose folder

```bash
cd deploy/docker
```

### 2. Build and start services

```bash
docker-compose up --build
```

This will start:

* MongoDB (mongo container)
* Nanda index on port 6900

Check service health:

```
http://localhost:6900/health
```

### 3. Optional environment variables
| Variable        | Default                     | Description                        |
|-----------------|----------------------------|------------------------------------|
| PORT            | 6900                        | Port for registry service          |
| CERT_DIR        | /certs                       | Directory containing SSL certs     |
| MONGODB_URI     | mongodb://mongo:27017/nanda | MongoDB connection URI             |
| WORKERS         | 2                            | Gunicorn worker count              |
| THREADS         | 2                            | Gunicorn threads per worker        |
