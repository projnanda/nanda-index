# registry.py
from flask import Flask, request, jsonify
import json
import os
import random
from datetime import datetime
from flask_cors import CORS
import requests
# MongoDB integration
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from apscheduler.schedulers.background import BackgroundScheduler
import urllib.parse
from apscheduler.schedulers.background import BackgroundScheduler
import time

app = Flask(__name__)
CORS(app)

# File to store the registry
DEFAULT_PORT = 6900


# --- MongoDB integration (no file fallback) ---
MONGO_URI = os.getenv("MONGODB_URI") or os.getenv("MONGO_URI") 

MONGO_DBNAME = os.getenv("MONGODB_DB", "iot_agents_db")

print(MONGO_DBNAME)


try:
    mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    mongo_client.admin.command("ping")  # Verify connection
    mongo_db = mongo_client[MONGO_DBNAME]

    agent_registry_col = mongo_db["agent_registry"]
    client_registry_col = mongo_db["client_registry"]
    users_col = mongo_db["users"]


    messages_col = mongo_db["messages"]  # For agent logs
    
    USE_MONGO = True
    print("Connected to MongoDB successfully – using MongoDB for persistence.")
except Exception as e:
    print(f"[registry] ERROR: Could not connect to MongoDB ({e}). Exiting.")
    exit(1)

# ---------------- Initial Data Load ------------------------
# Reconstruct `registry` dict from MongoDB
registry = {"agent_status": {}}
try:
    for doc in agent_registry_col.find():
        agent_id = doc.get("agent_id")
        if not agent_id:
            continue
        registry[agent_id] = doc.get("agent_url")
        registry["agent_status"][agent_id] = {
            "alive": doc.get("alive", False),
            "assigned_to": doc.get("assigned_to"),
            "last_update": doc.get("last_update"),
            "api_url": doc.get("api_url"),
            "unresponsive_count": doc.get("unresponsive_count",0)
        }
    print(f"[registry] Loaded {len(registry) - 1} agents from MongoDB")
except Exception as e:
    print(f"[registry] Error loading agent registry from MongoDB: {e}")
    registry = {"agent_status": {}}


# Reconstruct `client_registry` dict from MongoDB
client_registry = {"agent_map": {}}
try:
    for doc in client_registry_col.find():
        client_name = doc.get("client_name")
        if not client_name:
            continue
        client_registry[client_name] = doc.get("api_url")  # Store api_url, not client_url
        client_registry["agent_map"][client_name] = doc.get("agent_id")
    print(f"[registry] Loaded {len(client_registry) - 1} clients from MongoDB")
except Exception as e:
    print(f"[registry] Error loading client registry from MongoDB: {e}")
    client_registry = {"agent_map": {}}

# ---------------------------------------------------------------------------

# ---------------- Define helper functions BEFORE routes -------------------

def save_client_registry():
    """Persist the client registry to MongoDB only."""
    try:
        for client_name, api_url in client_registry.items():
            if client_name == 'agent_map':
                continue
            agent_id = client_registry.get('agent_map', {}).get(client_name)
            client_registry_col.update_one(
                {"client_name": client_name},
                {"$set": {"api_url": api_url, "agent_id": agent_id}},  # Store api_url correctly
                upsert=True,
            )
    except Exception as e:
        print(f"[registry] Error saving client registry to MongoDB: {e}")

def save_registry():
    """Persist the agent registry to MongoDB only."""
    try:
        for agent_id, agent_url in registry.items():
            if agent_id == 'agent_status':
                continue
            status = registry.get('agent_status', {}).get(agent_id, {})
            mongo_doc = {
                "agent_id": agent_id,
                "agent_url": agent_url,
                **status
            }
            agent_registry_col.update_one(
                {"agent_id": agent_id},
                {"$set": mongo_doc},
                upsert=True,
            )
    except Exception as e:
        print(f"[registry] Error saving agent registry to MongoDB: {e}")

def update_agent_status_field(agent_id, field_updates):
    """Update specific fields for a specific agent in MongoDB.
    
    Args:
        agent_id (str): The agent ID to update
        field_updates (dict): Dictionary of field names and values to update
    """
    try:
        # Update the in-memory registry first
        if agent_id in registry.get('agent_status', {}):
            for field, value in field_updates.items():
                registry['agent_status'][agent_id][field] = value
        
        # Update MongoDB with only the specified fields
        update_doc = {}
        for field, value in field_updates.items():
            update_doc[field] = value
            
        result = agent_registry_col.update_one(
            {"agent_id": agent_id},
            {"$set": update_doc}
        )
        
        if result.matched_count > 0:
            print(f"[registry] Updated {agent_id} fields: {list(field_updates.keys())}")
        else:
            print(f"[registry] Warning: Agent {agent_id} not found in MongoDB for field update")
            
    except Exception as e:
        print(f"[registry] Error updating agent {agent_id} fields in MongoDB: {e}")

# --------------------------------------------------------------------------

@app.route('/api/allocate', methods=['POST'])
def allocate_agent():
    data = request.json
    if not data or 'client_id' not in data:
        return jsonify({"error": "Missing client_name"}), 400
    
    str_name = data['userProfile']['name']
    client_name = str_name.replace(" ", "").lower()
    
    print("Client Name: ", client_name)

    # Check if this client already has an agent
    if client_name in client_registry:
        agent_id = client_registry['agent_map'][client_name]
        api_url = client_registry[client_name]  # This is the API URL
        agent_url = registry[agent_id]  # Get bridge URL from main registry
        
        return jsonify({
            "status": "allocated",
            "message": f"Client {client_name} is already allocated.. try a different name",
            "agent_url": agent_url,  # Bridge URL
            "api_url": api_url       # API URL
        })
  
    # Find an available agent from the main registry
    available_agents = []
    
    # First, find all allocated agent IDs
    assigned_agent_ids = set()
    for key, value in client_registry.items():
        if key == "agent_map":
            continue
        agent_id = client_registry['agent_map'][key]
        assigned_agent_ids.add(agent_id)
    
    # Loop through all agents in the registry to find available ones
    for agent_id, agent_url in registry.items():
        if agent_id != 'agent_status' and agent_id.split('agent')[1][0] == 'm' and agent_id not in assigned_agent_ids:
            available_agents.append((agent_id, agent_url))
    
    if not available_agents:
        return jsonify({"error": "No available agents at this time"}), 503
    # Select a random available agent
    selected_agent_id, selected_agent_url = random.choice(available_agents)
    api_url = registry['agent_status'][selected_agent_id]['api_url']
    
    print(f"Selected Agent URL (bridge): {selected_agent_url}")
    print(f"API URL for client: {api_url}")
    
    # Assign the agent to this client - store API URL in client registry
    client_registry[client_name] = api_url  # Store API URL, not agent URL
    
    # client-name to agent-id mapping
    if 'agent_map' not in client_registry:
        client_registry['agent_map'] = {}

    client_registry['agent_map'][client_name] = selected_agent_id

    save_client_registry()

    print("Selected Agent ID: ", selected_agent_id)

    # Update agent status to show it's alive and assigned to this client
    if 'agent_status' in registry and selected_agent_id in registry['agent_status']:
        registry['agent_status'][selected_agent_id]['alive'] = True
        registry['agent_status'][selected_agent_id]['assigned_to'] = client_name
        registry['agent_status'][selected_agent_id]['last_update'] = datetime.now().isoformat()
        save_registry()
    
    # Return the assigned agent info
    return jsonify({
        "status": "success",
        "agent_url": selected_agent_url,  # bridge URL
        "api_url": api_url,               # API URL
        "message": f"Agent {selected_agent_id} assigned to {client_name}"
    })

@app.route('/register', methods=['POST'])
def register():
    data = request.json
    if not data or 'agent_id' not in data or 'agent_url' not in data:
        return jsonify({"error": "Missing agent_id or agent_url"}), 400
    
    agent_id = data['agent_id']
    agent_url = data['agent_url'] 
    api_url = data['api_url'] # URL for the API PORT

    # Store the agent URL in the registry
    registry[agent_id] = agent_url

    # Initialize or update the agent_status section
    if 'agent_status' not in registry:
        registry['agent_status'] = {}
    
    # Set default status values
    registry['agent_status'][agent_id] = {
        'alive': False,
        'assigned_to': None,
        'api_url': api_url,
        'last_update': datetime.now().isoformat()
    }
    
    # Save the updated registry
    save_registry()
    
    return jsonify({"status": "success", "message": f"Agent {agent_id} registered successfully"})

@app.route('/lookup/<id>', methods=['GET'])
def lookup(id):
    """
    Lookup an agent by either agent_id or client_name
    """
    # First, try looking up by agent_id
    if id in registry and id != 'agent_status':
        # Direct lookup in agent registry
        agent_url = registry[id]
        api_url = registry['agent_status'][id].get('api_url')
        return jsonify({
            "agent_id": id, 
            "agent_url": agent_url,
            "api_url": api_url
        })
    
    # Next, try looking up by client_name
    if id in client_registry:
        # Get the agent info for this client
        agent_id = client_registry["agent_map"][id]
        agent_url = registry[agent_id]  # Bridge URL from main registry
        api_url = client_registry[id]   # API URL from client registry

        return jsonify({
            "agent_id": agent_id,
            "agent_url": agent_url,  # Bridge URL
            "api_url": api_url       # API URL
        }) 
    
    # If not found in either registry
    return jsonify({"error": f"ID '{id}' not found"}), 404

@app.route('/sender/<agent_id>', methods=['GET'])
def resolve_sender(agent_id):
    if not agent_id in registry['agent_status']:
        return jsonify({"error": "Unassigned agent"}), 400

    try:
        sender_name = registry['agent_status'][agent_id]['assigned_to']
        print("Sender name: ", sender_name) 
        return jsonify({'sender_name': sender_name})
    except:
        return jsonify({"error": "No client alive for this agent"}), 404

@app.route('/list', methods=['GET'])
def list_agents():
    # Return the registry (excluding agent_status for cleaner output)
    result = {k: v for k, v in registry.items() if k != 'agent_status'}
    return jsonify(result)

@app.route('/status/<agent_id>', methods=['GET'])
def agent_status(agent_id):
    """Return the status of all agents"""
    if 'agent_status' in registry:
        return jsonify(registry['agent_status'][agent_id]["alive"])
    return jsonify({})

@app.route('/clients', methods=['GET'])
def list_clients():
    """Return the client registry"""
    result = {k: 'alive' for k, v in client_registry.items() if k != 'agent_map'}
    return jsonify(result)

@app.route('/api/check-user', methods=['POST'])
def check_user():
    data = request.json
    email = data.get('email')
    if not email:
        return jsonify({'error': 'Missing email'}), 400

    if USE_MONGO:
        user = users_col.find_one({'email': email})
        if user:
            return jsonify({'exists': True, 'user': {'email': user['email'], 'username': user.get('username')}})
        else:
            return jsonify({'exists': False})
    else:
        return jsonify({'error': 'MongoDB not available'}), 500

@app.route('/api/signup', methods=['POST'])
def signup():
    data = request.json
    email = data.get('email')
    username = data.get('username')

    if not email or not username:
        return jsonify({'status': 'error', 'message': 'Missing email or username'}), 400

    if not USE_MONGO:
        return jsonify({'status': 'error', 'message': 'MongoDB not available'}), 500

    # Check if user already exists
    user = users_col.find_one({'email': email})
    if user:
        return jsonify({'status': 'error', 'message': 'User already exists'}), 400

    # Find an available agent
    assigned_agent_ids = set()
    for client, agent_id in client_registry.get('agent_map', {}).items():
        assigned_agent_ids.add(agent_id)
    available_agents = [aid for aid in registry if aid != 'agent_status' and aid.split('agent')[1][0] == 'm' and aid not in assigned_agent_ids]
    if not available_agents:
        return jsonify({'status': 'error', 'message': 'No available agents'}), 503
    selected_agent_id = random.choice(available_agents)
    agent_url = registry[selected_agent_id]
    api_url = registry['agent_status'][selected_agent_id].get('api_url')

    # Create user in MongoDB
    user_doc = {
        'email': email,
        'username': username,
        'agent_id': selected_agent_id,
        'agent_url': agent_url,
        'api_url': api_url
    }
    users_col.insert_one(user_doc)

    # Remove _id if present (it will be added by MongoDB but not in user_doc here)
    user_doc.pop('_id', None)

    # Assign agent to user in client_registry - store API URL
    client_registry[username] = api_url  # Store API URL, not agent URL
    if 'agent_map' not in client_registry:
        client_registry['agent_map'] = {}
    client_registry['agent_map'][username] = selected_agent_id
    save_client_registry()

    # Update agent status
    if 'agent_status' in registry and selected_agent_id in registry['agent_status']:
        registry['agent_status'][selected_agent_id]['alive'] = True
        registry['agent_status'][selected_agent_id]['assigned_to'] = username
        registry['agent_status'][selected_agent_id]['last_update'] = datetime.now().isoformat()
        save_registry()

    return jsonify({'status': 'success', 'user': user_doc, 'agent_url': agent_url, 'api_url': api_url})

@app.route('/api/setup', methods=['POST'])
def setup():
    data = request.json
    email = data.get('email')
    user_selected_agent_id = data.get('agent_id')
    username = data.get('username')

    if not email or not username or not user_selected_agent_id:
        return jsonify({'status': 'error', 'message': 'Missing email or username or agent_id'}), 400
    
    if not user_selected_agent_id.split("agent")[1][0].lower() == "s":
        return jsonify({'status': 'error', 'message': 'Invalid agent_id'}), 400

    if not user_selected_agent_id in registry:
        return jsonify({'status': 'error', 'message': 'Agent not found'}), 400

    assigned_agent_ids = set()
    for client, agent_id in client_registry.get('agent_map', {}).items():
        assigned_agent_ids.add(agent_id)

    if user_selected_agent_id in assigned_agent_ids:
        return jsonify({'status': 'error', 'message': 'Agent already assigned to a user'}), 400



    if not USE_MONGO:
        return jsonify({'status': 'error', 'message': 'MongoDB not available'}), 500

    # Check if user already exists
    user = users_col.find_one({'email': email})
    if user:
        return jsonify({'status': 'error', 'message': 'User already exists'}), 400

    # Assign agent to user in client_registry - store API URL
    agent_url = registry[user_selected_agent_id]
    api_url = registry['agent_status'][user_selected_agent_id].get('api_url')

    # Create user in Users MongoDB
    user_doc = {
        'email': email,
        'username': username,
        'agent_id': user_selected_agent_id,
        'agent_url': agent_url,
        'api_url': api_url
    }
    users_col.insert_one(user_doc)

    # Remove _id if present (it will be added by MongoDB but not in user_doc here) NOT NEEDED IDEALLY
    user_doc.pop('_id', None)

    # Assign agent to user in client_registry - store API URL
    client_registry[username] = api_url  # Store API URL, not agent URL
    if 'agent_map' not in client_registry:
        client_registry['agent_map'] = {}
    client_registry['agent_map'][username] = user_selected_agent_id
    save_client_registry()

    # Update agent status
    if 'agent_status' in registry and user_selected_agent_id in registry['agent_status']:
        registry['agent_status'][user_selected_agent_id]['alive'] = True
        registry['agent_status'][user_selected_agent_id]['assigned_to'] = username
        registry['agent_status'][user_selected_agent_id]['last_update'] = datetime.now().isoformat()
        save_registry()

    return jsonify({'status': 'success', 'user': user_doc, 'agent_url': agent_url, 'api_url': api_url})

def check_agent_health():
    print(f"[{datetime.now()}] Running health check...")
    
    # Check health for each agent in the registry
    for agent_id, bridge_url in registry.items():
        if agent_id == 'agent_status':
            continue
            
        # Get the agent status info
        agent_status = registry.get('agent_status', {}).get(agent_id, {})
        api_url = agent_status.get('api_url')
        
        if not api_url:
            print(f"[{datetime.now()}] Agent {agent_id} has no API URL, skipping health check")
            continue
            
        # Construct health check URL
        health_url = f"{api_url}/api/health"
        current_count = agent_status.get('unresponsive_count', 0)
        
        try:
            # Make health check request with timeout
            response = requests.get(health_url, timeout=5)
            
            if response.status_code == 200:
                # Agent is healthy - reset unresponsive count if it was > 0
                if current_count > 0:
                    update_agent_status_field(agent_id, {'unresponsive_count': 0})
                    print(f"[{datetime.now()}] Agent {agent_id} is healthy again, reset unresponsive count")
                else:
                    print(f"[{datetime.now()}] Agent {agent_id} is healthy")
            else:
                # Agent responded but with non-200 status
                new_count = current_count + 1
                update_agent_status_field(agent_id, {'unresponsive_count': new_count})
                print(f"[{datetime.now()}] Agent {agent_id} responded with status {response.status_code}, unresponsive count: {new_count}")
                
        except requests.exceptions.RequestException as e:
            # Agent is unresponsive
            new_count = current_count + 1
            update_agent_status_field(agent_id, {'unresponsive_count': new_count})
            print(f"[{datetime.now()}] Agent {agent_id} is unresponsive ({e}), unresponsive count: {new_count}")
    
    print(f"[{datetime.now()}] Health check completed")
    
    # Also log to a file for easier tracking
    try:
        os.makedirs("/opt/nanda-index/logs", exist_ok=True)
        with open("/opt/nanda-index/logs/health_check.log", "a") as f:
            f.write(f"[{datetime.now()}] Health check executed - {len([k for k in registry.keys() if k != 'agent_status'])} agents checked\n")
    except Exception as e:
        print(f"[{datetime.now()}] Could not write to log file: {e}")

def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=check_agent_health, trigger="interval", minutes=5)
    scheduler.start()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', DEFAULT_PORT))
    cert_dir = os.environ.get('CERT_DIR')
    
    if cert_dir:
        cert_path = os.path.join(cert_dir, "fullchain.pem")
        key_path = os.path.join(cert_dir, "privkey.pem")
        
        if os.path.exists(cert_path) and os.path.exists(key_path):
            app.run(
                ssl_context=(cert_path, key_path),
                host='0.0.0.0',
                port=port
            )
        else:
            print("Certificate files not found. Running without SSL...")
            app.run(host='0.0.0.0', port=port)
    else:
        print("No certificate directory specified. Running without SSL...")
        app.run(host='0.0.0.0', port=port)

