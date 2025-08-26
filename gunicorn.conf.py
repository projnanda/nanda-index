# Gunicorn configuration file
import os
import multiprocessing

import logging
logger = logging.getLogger("gunicorn.error")
logger.setLevel(logging.INFO)

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
project_root = os.path.dirname(os.path.abspath(__file__))
logs_dir = os.path.join(project_root, "logs")
os.makedirs(logs_dir, exist_ok=True)

accesslog = os.path.join(logs_dir, "access.log")
errorlog = os.path.join(logs_dir, "error.log")
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


# starting scheduler in master process
# def on_starting(server):
#     logger.info("[Gunicorn] on_starting hook called!")
#     try:
#         from registry import start_scheduler
#         logger.info("[Gunicorn] Starting scheduler in master process...")
#         start_scheduler()
#         logger.info("[Gunicorn] Scheduler started successfully!")
#     except Exception as e:
#         logger.error(f"[Gunicorn] Error starting scheduler: {e}")
#         import traceback
#         logger.error(f"[Gunicorn] Traceback: {traceback.format_exc()}")

scheduler_started = False
# Alternative hook - when server is ready
def when_ready(server):
    global scheduler_started
    if scheduler_started:
        return
    scheduler_started = True
    logger.info("[Gunicorn] when_ready hook called!")
    try:
        from registry import start_scheduler
        logger.info("[Gunicorn] Starting scheduler in when_ready...")
        start_scheduler()
        logger.info("[Gunicorn] Scheduler started successfully in when_ready!")
    except Exception as e:
        logger.error(f"[Gunicorn] Error starting scheduler in when_ready: {e}")
        import traceback
        logger.error(f"[Gunicorn] Traceback: {traceback.format_exc()}")