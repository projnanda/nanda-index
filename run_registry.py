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

def setup_certificates(domain):
    """Set up SSL certificates using certbot"""
    cert_dir = os.path.join(os.path.expanduser("~"), "certificates")
    os.makedirs(cert_dir, exist_ok=True)
    
    # Check if certbot is installed
    if shutil.which("certbot") is None:
        print("Installing certbot...")
        subprocess.run(["sudo", "apt-get", "update"])
        subprocess.run(["sudo", "apt-get", "install", "-y", "certbot"])
    
    # Stop any existing registry process that might be using port 80
    subprocess.run(["sudo", "pkill", "-f", "registry.py"], stderr=subprocess.DEVNULL)
    
    try:
        # Obtain certificate
        print(f"Obtaining SSL certificate for {domain}...")
        result = subprocess.run([
            "sudo", "certbot", "certonly", "--standalone",
            "-d", domain,
            "--agree-tos",
            "--non-interactive",
            "--email", "admin@nanda-registry.com"
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"Error obtaining certificate: {result.stderr}")
            return None
        
        # Copy certificates to our directory
        cert_path = f"/etc/letsencrypt/live/{domain}"
        if os.path.exists(cert_path):
            shutil.copy(os.path.join(cert_path, "fullchain.pem"), 
                       os.path.join(cert_dir, "fullchain.pem"))
            shutil.copy(os.path.join(cert_path, "privkey.pem"), 
                       os.path.join(cert_dir, "privkey.pem"))
            
            # Set proper permissions
            os.chmod(os.path.join(cert_dir, "fullchain.pem"), 0o644)
            os.chmod(os.path.join(cert_dir, "privkey.pem"), 0o600)
            
            return cert_dir
    except Exception as e:
        print(f"Error setting up certificates: {e}")
        return None
    
    return None

# Global process variables for cleanup
registry_process = None
SERVER_IP = get_local_ip()

def cleanup(signum=None, frame=None):
    """Clean up processes on exit"""
    global registry_process
    
    print("Cleaning up processes...")
    if registry_process:
        registry_process.terminate()
    
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
    
    try:
        registry_process = subprocess.Popen(
            ["python3", "registry.py"],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
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
    main()
