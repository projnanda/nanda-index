# Gunicorn configuration file
import os
import multiprocessing

# Server socket
bind = "0.0.0.0:6900"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
timeout = 30
keepalive = 2

# Restart workers after this many requests, to help prevent memory leaks
max_requests = 1000
max_requests_jitter = 50

# Logging
accesslog = "/opt/nanda-index/logs/access.log"
errorlog = "/opt/nanda-index/logs/error.log"
loglevel = "info"

# Process naming
proc_name = "nanda-registry"

# SSL Configuration (if certificates are available)
cert_dir = os.environ.get('CERT_DIR')
if cert_dir:
    cert_path = os.path.join(cert_dir, "fullchain.pem")
    key_path = os.path.join(cert_dir, "privkey.pem")
    
    if os.path.exists(cert_path) and os.path.exists(key_path):
        keyfile = key_path
        certfile = cert_path
        print(f"SSL enabled with certificates from: {cert_dir}")
    else:
        print("Certificate files not found. Running without SSL...")
else:
    print("No certificate directory specified. Running without SSL...")

# Preload app for better performance
preload_app = True

# Worker timeout
graceful_timeout = 30

# Server mechanics
daemon = False
pidfile = "/tmp/gunicorn-nanda-registry.pid"
user = None
group = None
tmp_upload_dir = None

# SSL
ssl_version = "TLSv1_2"
do_handshake_on_connect = False 