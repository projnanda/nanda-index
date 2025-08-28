# run_registry.py
import os
import subprocess
import time
import requests
import sys
import signal
import argparse
import socket
import shutil
from urllib.parse import urlparse

def get_virtual_env_path():
    """Dynamically detect the virtual environment path"""
    # Check if we're in a virtual environment
    venv_path = os.environ.get('VIRTUAL_ENV')
    if venv_path:
        bin_path = os.path.join(venv_path, 'bin')
        if os.path.exists(bin_path):
            return bin_path
    
    # Check common virtual environment locations
    common_venv_names = ['venv', 'env', '.venv', '.env', 'jinoos']
    current_dir = os.getcwd()
    
    for venv_name in common_venv_names:
        venv_dir = os.path.join(current_dir, venv_name)
        bin_dir = os.path.join(venv_dir, 'bin')
        if os.path.exists(bin_dir):
            return bin_dir
    
    # If no virtual environment found, return None
    return None

def find_gunicorn_executable():
    """Find gunicorn executable, checking virtual environment first, then system"""
    # First check virtual environment
    venv_bin_path = get_virtual_env_path()
    if venv_bin_path:
        gunicorn_path = os.path.join(venv_bin_path, 'gunicorn')
        if os.path.exists(gunicorn_path):
            return gunicorn_path, f"virtual environment ({venv_bin_path})"
    
    # Check if gunicorn is available in system PATH
    import shutil
    system_gunicorn = shutil.which('gunicorn')
    if system_gunicorn:
        return system_gunicorn, "system PATH"
    
    return None, None

def get_local_ip():
    """Get the local IP address of the system"""
    try:
        # Create a socket connection to an external server to determine the local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception as e:
        print(f"Error getting local IP: {e}")
        return "127.0.0.1"  # Fallback to localhost if we can't determine IP

def check_port_80():
    """Check what's using port 80 and try to handle it"""
    try:
        # First check what's using port 80
        result = subprocess.run(
            ["sudo", "lsof", "-i", ":80"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print("Process using port 80:")
            print(result.stdout)
            
            # Try to stop common web servers
            for service in ['apache2', 'nginx', 'httpd']:
                try:
                    # First try systemctl
                    subprocess.run(["sudo", "systemctl", "stop", service], 
                                 stderr=subprocess.DEVNULL)
                    print(f"Stopped {service} via systemctl")
                    
                    # If it's nginx, also try direct kill
                    if service == 'nginx':
                        # Get nginx PIDs
                        nginx_pids = subprocess.run(
                            ["pgrep", "nginx"],
                            capture_output=True,
                            text=True
                        )
                        if nginx_pids.returncode == 0:
                            for pid in nginx_pids.stdout.strip().split('\n'):
                                try:
                                    os.kill(int(pid), signal.SIGTERM)
                                    print(f"Sent SIGTERM to nginx process {pid}")
                                except:
                                    pass
                except:
                    pass
            
            # Wait longer for the port to be released
            print("Waiting for port 80 to be released...")
            for _ in range(5):  # Try for 5 seconds
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        s.bind(('', 80))
                        s.close()
                        print("Port 80 is now available")
                        return True
                except:
                    time.sleep(1)
                    continue
            
            # If we get here, port is still in use
            print("Port 80 is still in use after stopping services")
            return False
        else:
            print("No process found using port 80")
            return True
            
    except Exception as e:
        print(f"Error checking port 80: {e}")
        return False

def setup_certificates(domain):
    """Set up SSL certificates using certbot"""
    try:
        cert_dir = os.path.join(os.path.expanduser("~"), "certificates")
        print(f"Creating certificate directory at: {cert_dir}")
        os.makedirs(cert_dir, exist_ok=True)
        
        # Check if certbot is installed
        if shutil.which("certbot") is None:
            print("Installing certbot...")
            result = subprocess.run(["sudo", "apt-get", "update"], capture_output=True, text=True)
            print(f"apt-get update output: {result.stdout}")
            if result.stderr:
                print(f"apt-get update errors: {result.stderr}")
                
            result = subprocess.run(["sudo", "apt-get", "install", "-y", "certbot"], capture_output=True, text=True)
            print(f"certbot installation output: {result.stdout}")
            if result.stderr:
                print(f"certbot installation errors: {result.stderr}")
        
        # Stop any existing registry process that might be using port 80
        print("Checking for existing processes...")
        try:
            # Get current process ID
            current_pid = os.getpid()
            
            # Check for other registry processes (excluding current process)
            check_process = subprocess.run(
                ["pgrep", "-f", "registry.py"], 
                capture_output=True, 
                text=True
            )
            
            if check_process.returncode == 0:
                # Get list of PIDs
                pids = check_process.stdout.strip().split('\n')
                # Filter out current process
                other_pids = [pid for pid in pids if pid and int(pid) != current_pid]
                
                if other_pids:
                    print(f"Found {len(other_pids)} other registry processes, stopping them...")
                    for pid in other_pids:
                        try:
                            os.kill(int(pid), signal.SIGTERM)
                        except ProcessLookupError:
                            pass  # Process already gone
                    print("Other processes stopped")
                else:
                    print("No other registry processes found")
            else:
                print("No existing registry processes found")
        except Exception as e:
            print(f"Error checking/killing processes: {e}")
            # Continue anyway as this is not critical
        
        # Check if port 80 is available and try to free it
        print("Checking if port 80 is available...")
        if not check_port_80():
            print("Could not free port 80. Please manually stop any services using port 80.")
            print("Common services to check: apache2, nginx, httpd")
            return None
        
        print("Port 80 is available for certificate challenge")
        
        # Obtain certificate
        print(f"Obtaining SSL certificate for {domain}...")
        result = subprocess.run([
            "sudo", "certbot", "certonly", "--standalone",
            "-d", domain,
            "--agree-tos",
            "--non-interactive",
            "--email", "admin@nanda-registry.com"
        ], capture_output=True, text=True)
        
        print(f"Certbot output: {result.stdout}")
        if result.stderr:
            print(f"Certbot errors: {result.stderr}")
        
        if result.returncode != 0:
            print(f"Error obtaining certificate: {result.stderr}")
            return None
        
        # Copy certificates to our directory
        cert_path = f"/etc/letsencrypt/live/{domain}"
        print(f"Looking for certificates in: {cert_path}")
        
        if os.path.exists(cert_path):
            print("Found certificate directory, copying certificates...")
            try:
                # Read the actual certificate files (following symlinks)
                with open(os.path.join(cert_path, "fullchain.pem"), 'rb') as src:
                    with open(os.path.join(cert_dir, "fullchain.pem"), 'wb') as dst:
                        dst.write(src.read())
                
                with open(os.path.join(cert_path, "privkey.pem"), 'rb') as src:
                    with open(os.path.join(cert_dir, "privkey.pem"), 'wb') as dst:
                        dst.write(src.read())
                
                # Set proper permissions
                os.chmod(os.path.join(cert_dir, "fullchain.pem"), 0o644)
                os.chmod(os.path.join(cert_dir, "privkey.pem"), 0o600)
                
                print("Certificates copied successfully")
                return cert_dir
            except Exception as e:
                print(f"Error copying certificates: {e}")
                return None
        else:
            print(f"Certificate directory not found at: {cert_path}")
            return None
            
    except Exception as e:
        print(f"Error in setup_certificates: {str(e)}")
        import traceback
        print("Full traceback:")
        print(traceback.format_exc())
        return None

# Global process variables for cleanup
registry_process = None
SERVER_IP = get_local_ip()

    # Create logs directory
logs_dir = "logs"
os.makedirs(logs_dir, exist_ok=True)
print(f"Logs directory created/verified: {logs_dir}")

log_file_path = "logs/master.log"
log_file = open(log_file_path, "a")

def cleanup(signum=None, frame=None):
    """Clean up processes on exit"""
    global registry_process
    
    print("Cleaning up processes...")
    if registry_process:
        try:
            registry_process.terminate()
            print("Registry process terminated")
        except Exception as e:
            print(f"Error terminating registry process: {e}")
    try:
        log_file.close()
    except:
        pass 
    sys.exit(0)

def get_ngrok_url():
    """Get the public URL from ngrok for port 6900"""
    try:
        response = requests.get("https://localhost:4040/api/tunnels")
        data = response.json()
        
        if "tunnels" in data and len(data["tunnels"]) > 0:
            for tunnel in data["tunnels"]:
                # Check if this tunnel is for port 6900
                if "addr" in tunnel.get("config", {}) and tunnel["config"]["addr"].endswith(":6900"):
                    return tunnel["public_url"]
            
            # If no specific tunnel for port 6900 is found, return the first one
            return data["tunnels"][0]["public_url"]
    except Exception as e:
        print(f"Error getting ngrok URL: {e}")
    return None

def main():
    global registry_process
    
    # Set up signal handlers for graceful exit
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)
    
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Start a registry server")
    parser.add_argument("--port", type=int, default=6900, help="Registry server port (default: 6900)")
    parser.add_argument("--public-url", help="Manually specify public URL (skips ngrok detection)")
    parser.add_argument("--use-gunicorn", action="store_true", help="Use Gunicorn instead of Flask development server")
    args = parser.parse_args()
    
    registry_port = args.port
    
    # Determine the public URL
    registry_url = None
    
    if args.public_url:
        # Use manually specified URL
        registry_url = args.public_url
        print(f"Using manually specified URL: {registry_url}")
    else:
        # Try to detect from existing ngrok
        registry_url = get_ngrok_url()
        
        if registry_url:
            print(f"Found existing ngrok tunnel: {registry_url}")
        else:
            print("No ngrok tunnel found and no --public-url specified.")
            print("Please either:")
            print("1. Start ngrok manually: ngrok http 6900")
            print("2. Provide a public URL: --public-url https://your-ngrok-url.app")
            sys.exit(1)
    
    # Extract domain from URL
    parsed_url = urlparse(registry_url)
    domain = parsed_url.netloc.split(':')[0]  # Remove port if present
    print(f"Extracted domain: {domain}")
    
    # Set up SSL certificates
    cert_dir = os.path.join(os.path.expanduser("~"), "certificates")
    cert_files_exist = (os.path.exists(os.path.join(cert_dir, "fullchain.pem")) and 
                       os.path.exists(os.path.join(cert_dir, "privkey.pem")))
    
    if cert_files_exist:
        print(f"SSL certificates already exist in: {cert_dir}")
        print("Skipping certificate generation...")
    else:
        print("Setting up SSL certificates...")
        cert_dir = setup_certificates(domain)
        if not cert_dir:
            print("Failed to set up SSL certificates. Running without SSL...")
            cert_dir = None
        else:
            print(f"SSL certificates set up successfully in: {cert_dir}")
    
    # Save the registry URL to a file
    with open("registry_url.txt", "w") as f:
        f.write(registry_url)
    
    print(f"Registry will be accessible at: {registry_url}")
    print(f"Saved URL to registry_url.txt")
    
    # Start the registry server with certificate information
    print(f"Starting registry server on port {registry_port}...")
    env = {**os.environ, "PORT": str(registry_port)}
    if cert_dir:
        env["CERT_DIR"] = cert_dir
        print(f"Certificate directory set in environment: {cert_dir}")
    
    try:
        print("Launching registry process...")
        
        if args.use_gunicorn:
            # Use Gunicorn
            gunicorn_path, source_info = find_gunicorn_executable()
            if gunicorn_path:
                cmd = [gunicorn_path, "-c", "gunicorn.conf.py", "registry:app"]
                print(f"Using Gunicorn server from {source_info}: {gunicorn_path}")
            else:
                print("ERROR: Gunicorn not found in virtual environment or system PATH!")
                print("Please install gunicorn:")
                print("  pip install gunicorn")
        else:
            # Use Flask development server
            cmd = ["python3", "registry.py"]
            print("Using Flask development server")
        
        registry_process = subprocess.Popen(
            cmd,
            env=env,
            stdout=log_file,
            stderr=log_file,
            text=True
        )
        
        # Check if process started successfully
        if registry_process.poll() is not None:
            stdout, stderr = registry_process.communicate()
            print("Registry process failed to start!")
            print("STDOUT:", stdout)
            print("STDERR:", stderr)
            sys.exit(1)
            
        print(f"Registry process started with PID: {registry_process.pid}")
        print(f"Registry is running at {registry_url}")
        print("Press Ctrl+C to stop all processes.")
        
        # Keep running until interrupted
        while True:
            if registry_process.poll() is not None:
                stdout, stderr = registry_process.communicate()
                print("Registry process stopped unexpectedly!")
                print("STDOUT:", stdout)
                print("STDERR:", stderr)
                sys.exit(1)
            time.sleep(1)
            
    except KeyboardInterrupt:
        cleanup()
    except Exception as e:
        print(f"Error starting registry: {e}")
        cleanup()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Unhandled exception: {e}")
        cleanup()
