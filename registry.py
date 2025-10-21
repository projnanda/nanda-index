# registry.py
from flask import Flask, request, jsonify
import os
import random
from datetime import datetime
from flask_cors import CORS
from typing import Any, Dict, List
from pathlib import Path
import json

TEST_MODE = os.getenv("TEST_MODE") == "1"

if not TEST_MODE:
    from pymongo import MongoClient


app = Flask(__name__)
CORS(app)

# File to store the registry
DEFAULT_PORT = 6900


# (Moved TEST_MODE definition above)

# --- MongoDB integration (no file fallback) ---
MONGO_URI = os.getenv("MONGODB_URI") or os.getenv("MONGO_URI")
MONGO_DBNAME = os.getenv("MONGODB_DB", "iot_agents_db")

if not TEST_MODE:
    try:  # Mongo optional initialization
        mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        mongo_client.admin.command("ping")
        mongo_db = mongo_client[MONGO_DBNAME]
        agent_registry_col = mongo_db.get_collection("agent_registry")
        client_registry_col = mongo_db.get_collection("client_registry")
        users_col = mongo_db.get_collection("users")
        mcp_registry_col = mongo_db.get_collection("mcp_registry")
        messages_col = mongo_db.get_collection("messages")
        USE_MONGO = True
        print("Connected to MongoDB successfully – using MongoDB for persistence.")
    except Exception as e:
        USE_MONGO = False
        agent_registry_col = None
        client_registry_col = None
        users_col = None
        mcp_registry_col = None
        messages_col = None
        print(f"[registry] WARN: MongoDB unavailable ({e}); continuing in in-memory mode.")
else:
    USE_MONGO = False
    agent_registry_col = None
    client_registry_col = None
    users_col = None
    mcp_registry_col = None
    messages_col = None
    print("[registry] TEST_MODE enabled – using in-memory registries (no MongoDB).")

# ---------------- Initial Data Load ------------------------
# Reconstruct `registry` dict from MongoDB
registry = {"agent_status": {}}
if not TEST_MODE and USE_MONGO and agent_registry_col is not None:
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
                "api_url": doc.get("api_url")
            }
        print(f"[registry] Loaded {len(registry) - 1} agents from MongoDB")
    except Exception as e:
        print(f"[registry] Error loading agent registry from MongoDB: {e}")
        registry = {"agent_status": {}}


# Reconstruct `client_registry` dict from MongoDB
client_registry = {"agent_map": {}}
if not TEST_MODE and USE_MONGO and client_registry_col is not None:
    try:
        for doc in client_registry_col.find():
            client_name = doc.get("client_name")
            if not client_name:
                continue
            client_registry[client_name] = doc.get("api_url")
            client_registry["agent_map"][client_name] = doc.get("agent_id")
        print(f"[registry] Loaded {len(client_registry) - 1} clients from MongoDB")
    except Exception as e:
        print(f"[registry] Error loading client registry from MongoDB: {e}")
        client_registry = {"agent_map": {}}

# ---------------------------------------------------------------------------

# ---------------- Define helper functions BEFORE routes -------------------

def save_client_registry():
    """Persist the client registry to MongoDB only (no-op in TEST_MODE)."""
    if TEST_MODE or not USE_MONGO or client_registry_col is None:
        return
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
    """Persist the agent registry to MongoDB only (no-op in TEST_MODE)."""
    if TEST_MODE or not USE_MONGO or agent_registry_col is None:
        return
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

# ---------------- New Extended Endpoints -----------------

@app.route('/health', methods=['GET'])
def health():
    """Simple health check endpoint."""
    return jsonify({"status": "ok", "mongo": USE_MONGO and not TEST_MODE})

@app.route('/stats', methods=['GET'])
def stats():
    """Return basic statistics about the registry."""
    agents = [a for a in registry.keys() if a != 'agent_status']
    total_agents = len(agents)
    alive_agents = 0
    if 'agent_status' in registry:
        alive_agents = sum(1 for a in agents if registry['agent_status'].get(a, {}).get('alive'))
    total_clients = len([c for c in client_registry.keys() if c != 'agent_map'])
    return jsonify({
        'total_agents': total_agents,
        'alive_agents': alive_agents,
        'total_clients': total_clients
    })

def _build_agent_payload(agent_id: str) -> Dict[str, Any]:
    """Construct a richer agent payload used by search and agent detail endpoints."""
    agent_url = registry.get(agent_id)
    status_obj = registry.get('agent_status', {}).get(agent_id, {})
    payload = {
        'agent_id': agent_id,
        'agent_url': agent_url,
        'api_url': status_obj.get('api_url'),
        'alive': status_obj.get('alive', False),
        'assigned_to': status_obj.get('assigned_to'),
        'last_update': status_obj.get('last_update'),
        # Placeholders – future enhancement can map capabilities/tags from annotations or other sources
        'capabilities': status_obj.get('capabilities', []),
        'tags': status_obj.get('tags', [])
    }
    return payload

@app.route('/search', methods=['GET'])
def search_agents():
    """Search agents by substring match and optional capabilities/tags filters.
    Query params:
      q: substring to match in agent_id
      capabilities: comma-separated capabilities
      tags: comma-separated tags
    """
    query = request.args.get('q', '').strip().lower()
    capabilities_filter = request.args.get('capabilities')
    tags_filter = request.args.get('tags')
    capabilities_list = [c.strip() for c in capabilities_filter.split(',')] if capabilities_filter else []
    tags_list = [t.strip() for t in tags_filter.split(',')] if tags_filter else []

    results: List[Dict[str, Any]] = []
    for agent_id in registry.keys():
        if agent_id == 'agent_status':
            continue
        if query and query not in agent_id.lower():
            continue
        payload = _build_agent_payload(agent_id)
        if capabilities_list:
            agent_caps = payload.get('capabilities', []) or []
            if not any(c in agent_caps for c in capabilities_list):
                continue
        if tags_list:
            agent_tags = payload.get('tags', []) or []
            if not any(t in agent_tags for t in tags_list):
                continue
        results.append(payload)
    return jsonify(results)

@app.route('/agents/<agent_id>', methods=['GET'])
def get_agent(agent_id):
    if agent_id not in registry or agent_id == 'agent_status':
        return jsonify({'error': 'Agent not found'}), 404
    return jsonify(_build_agent_payload(agent_id))

@app.route('/agents/<agent_id>', methods=['DELETE'])
def delete_agent(agent_id):
    if agent_id not in registry or agent_id == 'agent_status':
        return jsonify({'error': 'Agent not found'}), 404
    # Remove from registries
    registry.pop(agent_id, None)
    if 'agent_status' in registry:
        registry['agent_status'].pop(agent_id, None)
    # Remove any client assignments
    to_remove = []
    for client_name, mapped_agent in client_registry.get('agent_map', {}).items():
        if mapped_agent == agent_id:
            to_remove.append(client_name)
    for client_name in to_remove:
        client_registry.pop(client_name, None)
        client_registry.get('agent_map', {}).pop(client_name, None)
    save_registry()
    save_client_registry()
    return jsonify({'status': 'deleted', 'agent_id': agent_id})

@app.route('/agents/<agent_id>/status', methods=['PUT'])
def update_agent_status(agent_id):
    if agent_id not in registry or agent_id == 'agent_status':
        return jsonify({'error': 'Agent not found'}), 404
    data = request.json or {}
    status_obj = registry.get('agent_status', {}).get(agent_id, {})
    # Update mutable fields
    if 'alive' in data:
        status_obj['alive'] = bool(data['alive'])
    if 'assigned_to' in data:
        status_obj['assigned_to'] = data['assigned_to']
    status_obj['last_update'] = datetime.now().isoformat()
    # Optional metadata extensions
    if 'capabilities' in data and isinstance(data['capabilities'], list):
        status_obj['capabilities'] = data['capabilities']
    if 'tags' in data and isinstance(data['tags'], list):
        status_obj['tags'] = data['tags']
    registry['agent_status'][agent_id] = status_obj
    save_registry()
    return jsonify({'status': 'updated', 'agent': _build_agent_payload(agent_id)})

@app.route('/mcp_servers', methods=['GET'])
def list_mcp_servers():
    """Return MCP servers registered. Currently stub bridging to any agents with record_type 'mcp' if stored.
    For now, return agents whose ID starts with 'mcp' or those with a capability 'mcp-server'."""
    results = []
    for agent_id in registry.keys():
        if agent_id == 'agent_status':
            continue
        status_obj = registry.get('agent_status', {}).get(agent_id, {})
        caps = status_obj.get('capabilities', []) or []
        if agent_id.startswith('mcp') or 'mcp-server' in caps:
            results.append(_build_agent_payload(agent_id))
    return jsonify(results)

# --------------------------------------------------------------------------

# --- Skill Mapping Support (lightweight integration) ----------------------
_skill_mapper = None
_skill_mapper_init_error = None
DEFAULT_OASF_SCHEMA_DIR = os.environ.get("OASF_SCHEMA_DIR", os.path.join(os.path.dirname(__file__), "../agntcy/oasf/schema"))

def _init_skill_mapper():
    global _skill_mapper, _skill_mapper_init_error
    if _skill_mapper is not None or _skill_mapper_init_error is not None:
        return
    schema_dir = Path(DEFAULT_OASF_SCHEMA_DIR).resolve()
    if not schema_dir.exists():
        _skill_mapper_init_error = f"Schema directory not found: {schema_dir}"
        return
    try:
        # Local minimal SkillMapper extracted from export script (duplicated to avoid import-time side effects)
        class SkillMapper:
            def __init__(self, schema_dir: Path):
                self.schema_dir = schema_dir
                self.categories: Dict[str, Dict[str, Any]] = {}
                self.skills: Dict[str, Dict[str, Any]] = {}
                self.leaf_skills: Dict[str, Dict[str, Any]] = {}
                self.children: Dict[str, List[str]] = {}
                self._load()
                self._compute_leaves()
            def _load(self):
                cat_file = self.schema_dir / 'skill_categories.json'
                if cat_file.exists():
                    try:
                        data = json.loads(cat_file.read_text(encoding='utf-8'))
                        for k,v in data.get('attributes', {}).items():
                            self.categories[k] = v
                    except Exception as e:
                        print(f"[skills] WARN categories load: {e}")
                skills_root = self.schema_dir / 'skills'
                if not skills_root.exists():
                    return
                for category_dir in skills_root.iterdir():
                    if not category_dir.is_dir():
                        continue
                    for json_file in category_dir.rglob('*.json'):
                        try:
                            obj = json.loads(json_file.read_text(encoding='utf-8'))
                            name = obj.get('name')
                            if not name:
                                continue
                            self.skills[name] = obj
                            parent = obj.get('extends')
                            if isinstance(parent, str):
                                self.children.setdefault(parent, []).append(name)
                        except Exception as e:
                            print(f"[skills] WARN skill load {json_file}: {e}")
            def _compute_leaves(self):
                parent_set = set(self.children.keys())
                for name, obj in self.skills.items():
                    if name not in parent_set or not self.children.get(name):
                        self.leaf_skills[name] = obj
            def map_capability(self, capability: str):
                cap_norm = capability.lower().strip().replace(' ', '_').replace('-', '_')
                if cap_norm in self.leaf_skills:
                    return self._payload(self.leaf_skills[cap_norm])
                for leaf in self.leaf_skills.values():
                    caption = (leaf.get('caption') or '').lower()
                    if cap_norm in caption:
                        return self._payload(leaf)
                rules = [
                    ('chat', 'natural_language_generation'),
                    ('conversation', 'natural_language_generation'),
                    ('classif', 'text_classification'),
                    ('retriev', 'information_retrieval_synthesis'),
                    ('search', 'information_retrieval_synthesis'),
                    ('vision', 'image_classification'),
                    ('image', 'image_classification'),
                    ('tool', 'tool_use_planning'),
                ]
                for needle, target in rules:
                    if needle in cap_norm and target in self.skills:
                        cand = self.skills[target]
                        if target not in self.leaf_skills and self.children.get(target):
                            child = self.children[target][0]
                            cand = self.skills.get(child, cand)
                        return self._payload(cand)
                return None
            def _payload(self, leaf: Dict[str, Any]):
                chain = []
                cur = leaf
                seen = set()
                while cur and isinstance(cur.get('extends'), str) and cur.get('extends') != 'base_skill':
                    parent_name = cur.get('extends')
                    if parent_name in seen:
                        break
                    seen.add(parent_name)
                    parent_obj = self.skills.get(parent_name)
                    if not parent_obj:
                        break
                    chain.append(parent_obj)
                    cur = parent_obj
                top_parent = chain[-1] if chain else leaf if leaf.get('extends') == 'base_skill' else None
                category_key = (top_parent or leaf).get('extends') if (top_parent or leaf) else None
                if category_key == 'base_skill':
                    category_key = leaf.get('name')
                cat_meta = self.categories.get(category_key, {}) if category_key else {}
                return {
                    'skill_id': leaf.get('name'),
                    'category_name': cat_meta.get('caption', category_key),
                    'category_uid': cat_meta.get('uid', 0),
                    'class_name': leaf.get('caption'),
                    'class_uid': leaf.get('uid', 0)
                }
        _skill_mapper = SkillMapper(schema_dir)
    except Exception as e:
        _skill_mapper_init_error = f"Initialization error: {e}"

@app.route('/skills/map')
def map_capability():
    """Map a free-form capability string to a skill taxonomy entry.
    Query params: capability=string
    Returns 404 if not mapped; includes diagnostics if initialization failed."""
    cap = request.args.get('capability', '').strip()
    if not cap:
        return jsonify({'error': 'Missing capability query param'}), 400
    _init_skill_mapper()
    if _skill_mapper_init_error:
        return jsonify({'error': 'mapper_init_failed', 'detail': _skill_mapper_init_error}), 500
    if not _skill_mapper:
        return jsonify({'error': 'mapper_unavailable'}), 500
    mapped = _skill_mapper.map_capability(cap)
    if not mapped:
        return jsonify({'capability': cap, 'mapped': None}), 404
    return jsonify({'capability': cap, 'mapped': mapped})

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
        if agent_id != 'agent_status' and agent_id.startswith('agentm') and agent_id not in assigned_agent_ids:
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

    # Persist immediately if Mongo available
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
    if agent_id not in registry['agent_status']:
        return jsonify({"error": "Unassigned agent"}), 400

    try:
        sender_name = registry['agent_status'][agent_id]['assigned_to']
        print("Sender name: ", sender_name)
        return jsonify({'sender_name': sender_name})
    except Exception:
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

    if USE_MONGO and not TEST_MODE and users_col is not None:
        user = users_col.find_one({'email': email})
        if user:
            return jsonify({'exists': True, 'user': {'email': user['email'], 'username': user.get('username')}})
        return jsonify({'exists': False})
    return jsonify({'error': 'MongoDB not available'}), 500

@app.route('/api/signup', methods=['POST'])
def signup():
    data = request.json
    email = data.get('email')
    username = data.get('username')

    if not email or not username:
        return jsonify({'status': 'error', 'message': 'Missing email or username'}), 400

    if not USE_MONGO or TEST_MODE:
        return jsonify({'status': 'error', 'message': 'MongoDB not available'}), 500

    # Check if user already exists
    if USE_MONGO and not TEST_MODE and users_col is not None:
        user = users_col.find_one({'email': email})
    else:
        user = None
    if user:
        return jsonify({'status': 'error', 'message': 'User already exists'}), 400

    # Find an available agent
    assigned_agent_ids = set()
    for client, agent_id in client_registry.get('agent_map', {}).items():
        assigned_agent_ids.add(agent_id)
    available_agents = [aid for aid in registry if aid != 'agent_status' and aid.startswith('agentm') and aid not in assigned_agent_ids]
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
    if USE_MONGO and not TEST_MODE and users_col is not None:
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
            # Persist status update
            save_registry()

    if user_selected_agent_id not in registry:
        return jsonify({'status': 'error', 'message': 'Agent not found'}), 400

    assigned_agent_ids = set()
    for client, agent_id in client_registry.get('agent_map', {}).items():
        assigned_agent_ids.add(agent_id)

    if user_selected_agent_id in assigned_agent_ids:
        return jsonify({'status': 'error', 'message': 'Agent already assigned to a user'}), 400



    if not USE_MONGO or TEST_MODE:
        return jsonify({'status': 'error', 'message': 'MongoDB not available'}), 500

    # Check if user already exists
    if USE_MONGO and not TEST_MODE and users_col is not None:
        user = users_col.find_one({'email': email})
    else:
        user = None
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
    if USE_MONGO and not TEST_MODE and users_col is not None:
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

@app.route('/get_mcp_registry', methods=['GET'])
def get_mcp_server_details():
    """
    Get MCP server details by registry_provider and qualified_name via query parameters
    """
    registry_provider = request.args.get('registry_provider')
    qualified_name = request.args.get('qualified_name')

    if not registry_provider or not qualified_name:
        return jsonify({
            "error": "Missing required query parameters: registry_provider and qualified_name"
        }), 400

    try:
        # Query the mcp_registry collection for the specified registry_provider and qualified_name
        mcp_doc = None
        if USE_MONGO and not TEST_MODE and mcp_registry_col is not None:
            mcp_doc = mcp_registry_col.find_one({
                "registry_provider": registry_provider,
                "qualified_name": qualified_name
            })

        if not mcp_doc:
            return jsonify({
                "error": f"MCP server not found for registry_provider: {registry_provider}, qualified_name: {qualified_name}"
            }), 404

        # Remove MongoDB's _id field from the response
        if '_id' in mcp_doc:
            del mcp_doc['_id']

        return jsonify(mcp_doc)

    except Exception as e:
        return jsonify({"error": f"Error retrieving MCP server details: {str(e)}"}), 500


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

