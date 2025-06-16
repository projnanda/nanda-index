# run_registry.py
import os
import subprocess
import time
import requests
import sys
import signal
import argparse
import socket

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
    
    # Save the registry URL to a file
    with open("registry_url.txt", "w") as f:
        f.write(registry_url)
    
    print(f"Registry will be accessible at: {registry_url}")
    print(f"Saved URL to registry_url.txt")
    
    # Start the registry server
    print(f"Starting registry server on port {registry_port}...")
    registry_process = subprocess.Popen(
        ["python3", "registry.py"],
        env={**os.environ, "PORT": str(registry_port)}
    )
    
    print(f"Registry is running at {registry_url}")
    print("Press Ctrl+C to stop all processes.")
    
    try:
        # Keep running until interrupted
        registry_process.wait()
    except KeyboardInterrupt:
        cleanup()

if __name__ == "__main__":
    main()
