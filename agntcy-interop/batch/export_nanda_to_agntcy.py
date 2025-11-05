#!/usr/bin/env python3
"""Export Nanda registry agents into OASF (AGNTCY) record JSON files.
Moved to agntcy-interop/ to keep root cleaner. See README in this folder.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
import requests

DEFAULT_REGISTRY_URL = os.environ.get("REGISTRY_URL", "http://localhost:6900")
DEFAULT_OASF_SCHEMA_DIR = os.environ.get("OASF_SCHEMA_DIR", "../agntcy/oasf/schema")
# Git clone configuration for taxonomy if local dir missing
GIT_TAXONOMY_REPO = os.environ.get("OASF_SCHEMA_GIT_REPO", "https://github.com/agntcy/oasf.git")
GIT_TAXONOMY_REF = os.environ.get("OASF_SCHEMA_GIT_REF", "main")
ENABLE_GIT_CLONE = os.environ.get("OASF_SCHEMA_GIT_CLONE", "1") == "1"

# ---------------- Enhanced Skill Mapping Support -----------------
class SkillMapper:
    def __init__(self, schema_dir: Path):
        # If local directory missing and cloning enabled, attempt git clone of taxonomy repo
        self.schema_dir = schema_dir
        if not self.schema_dir.exists() and ENABLE_GIT_CLONE:
            self._attempt_clone()
        self.categories: Dict[str, Dict[str, Any]] = {}
        self.skills: Dict[str, Dict[str, Any]] = {}
        self.leaf_skills: Dict[str, Dict[str, Any]] = {}
        self.children: Dict[str, List[str]] = {}
        self._load()
        self._compute_leaves()

    def _attempt_clone(self):
        try:
            # Determine repo root (assuming schema_dir ends with /schema)
            repo_root = self.schema_dir.parent if self.schema_dir.name == 'schema' else self.schema_dir
            if repo_root.exists():
                return  # Already present (maybe partial)
            repo_root.parent.mkdir(parents=True, exist_ok=True)
            print(f"[INFO] Cloning taxonomy repo {GIT_TAXONOMY_REPO} -> {repo_root}")
            import subprocess
            subprocess.run(['git', 'clone', '--depth', '1', '--branch', GIT_TAXONOMY_REF, GIT_TAXONOMY_REPO, str(repo_root)], check=False)
            if not self.schema_dir.exists():
                print(f"[WARN] Clone finished but schema directory not found at {self.schema_dir}")
        except Exception as e:
            print(f"[WARN] Git clone failed: {e}")

    def _load(self):
        # No remote_mode; we rely on local filesystem (clone may have populated it)
        # Local filesystem mode
        cat_file = self.schema_dir / 'skill_categories.json'
        if cat_file.exists():
            try:
                data = json.loads(cat_file.read_text(encoding='utf-8'))
                for k, v in data.get('attributes', {}).items():
                    self.categories[k] = v
            except Exception as e:
                print(f"[WARN] Failed loading skill categories: {e}")
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
                    print(f"[WARN] Failed loading skill {json_file}: {e}")

    def _compute_leaves(self):
        parent_set = set(self.children.keys())
        for name, obj in self.skills.items():
            if name not in parent_set or not self.children.get(name):
                self.leaf_skills[name] = obj

    def map_capability(self, capability: str) -> Optional[Dict[str, Any]]:
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

# ---------------- Registry fetch helpers -----------------

def fetch_agent_ids(registry_url: str) -> List[str]:
    resp = requests.get(f"{registry_url}/list", timeout=10, verify=False)
    resp.raise_for_status()
    data = resp.json()
    return list(data.keys())


def fetch_agent(registry_url: str, agent_id: str) -> Optional[Dict[str, Any]]:
    resp = requests.get(f"{registry_url}/agents/{agent_id}", timeout=10, verify=False)
    if resp.status_code == 200:
        return resp.json()
    return None


def parse_agent_id(agent_id: str) -> Tuple[str, str]:
    if ':' in agent_id:
        parts = agent_id.rsplit(':', 1)
        return parts[0], parts[1]
    return agent_id, 'v0'


def build_description(agent: Dict[str, Any]) -> str:
    parts = []
    caps = agent.get('capabilities') or []
    tags = agent.get('tags') or []
    if caps:
        parts.append("Capabilities: " + ", ".join(caps))
    if tags:
        parts.append("Tags: " + ", ".join(tags))
    if not parts:
        return f"Exported agent {agent.get('agent_id')} from Nanda registry."
    return f"Exported agent {agent.get('agent_id')} from Nanda registry. " + " | ".join(parts)


def build_locators(agent: Dict[str, Any]) -> List[Dict[str, str]]:
    locators = []
    if agent.get('agent_url'):
        locators.append({'type': 'bridge-url', 'url': agent['agent_url']})
    if agent.get('api_url'):
        locators.append({'type': 'api-url', 'url': agent['api_url']})
    return locators


def build_mcp_extension(agent: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    api_url = agent.get('api_url') or ''
    if not api_url.startswith('cmd://'):
        return None
    try:
        after = api_url[len('cmd://'):]
        if '?args=' in after:
            command, arg_str = after.split('?args=', 1)
            args = arg_str.split() if arg_str else []
        else:
            command, args = after, []
    except Exception:
        command, args = api_url, []
    return {
        'name': 'schema.oasf.agntcy.org/features/runtime/mcp',
        'version': 'v1.0.0',
        'data': {'servers': {'nanda-export': {'command': command, 'args': args, 'env': {}}}}
    }


def agent_to_oasf_record(agent: Dict[str, Any], mapper: Optional[SkillMapper] = None) -> Dict[str, Any]:
    name, version = parse_agent_id(agent.get('agent_id', 'unknown'))
    created_at = agent.get('last_update') or datetime.now(timezone.utc).isoformat()
    skills_list: List[Dict[str, Any]] = []
    seen_ids = set()
    if mapper:
        for cap in agent.get('capabilities', []) or []:
            mapped = mapper.map_capability(cap)
            if mapped and mapped['skill_id'] not in seen_ids:
                skills_list.append(mapped)
                seen_ids.add(mapped['skill_id'])
    record: Dict[str, Any] = {
        'name': name,
        'version': version,
        'description': build_description(agent),
        'authors': [],
        'created_at': created_at,
        'skills': skills_list,
        'locators': build_locators(agent),
        'extensions': [],
        'signature': {}
    }
    mcp_ext = build_mcp_extension(agent)
    if mcp_ext:
        record['extensions'].append(mcp_ext)
    return record


def export_agents(registry_url: str, out_dir: Path, agent_ids: List[str], dry_run: bool, limit: Optional[int], mapper: Optional[SkillMapper]) -> int:
    exported = 0
    if limit is not None:
        agent_ids = agent_ids[:limit]
    out_dir.mkdir(parents=True, exist_ok=True)
    for aid in agent_ids:
        agent = fetch_agent(registry_url, aid)
        if not agent:
            print(f"[WARN] Agent not found: {aid}")
            continue
        record = agent_to_oasf_record(agent, mapper=mapper)
        filename = f"{record['name'].replace('/', '-')}.record.json"
        if dry_run:
            print(f"[DRY] Would write {filename}:\n" + json.dumps(record, indent=2))
            exported += 1
            continue
        path = out_dir / filename
        with path.open('w', encoding='utf-8') as f:
            json.dump(record, f, indent=2)
        print(f"[OK] Exported {aid} -> {path}")
        exported += 1
    return exported


def main():
    parser = argparse.ArgumentParser(description='Export Nanda registry agents to OASF record JSON files')
    parser.add_argument('--registry-url', default=DEFAULT_REGISTRY_URL)
    parser.add_argument('--out-dir', default='./exported-oasf-records')
    parser.add_argument('--agent-id', help='Export only this agent ID')
    parser.add_argument('--agent-prefix', help='Only export agents whose ID starts with this prefix')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--oasf-schema-dir', default=DEFAULT_OASF_SCHEMA_DIR, help='Path to OASF schema root for skill mapping')
    parser.add_argument('--limit', type=int, default=None)
    args = parser.parse_args()
    try:
        if args.agent_id:
            agent_ids = [args.agent_id]
        else:
            agent_ids = fetch_agent_ids(args.registry_url)
            if args.agent_prefix:
                agent_ids = [a for a in agent_ids if a.startswith(args.agent_prefix)]
        if not agent_ids:
            print('[INFO] No agents to export.')
            return 1
        mapper = None
        schema_dir = Path(args.oasf_schema_dir)
        if schema_dir.exists():
            mapper = SkillMapper(schema_dir)
        count = export_agents(args.registry_url, Path(args.out_dir), agent_ids, args.dry_run, args.limit, mapper)
        print(f"[SUMMARY] Exported {count} agent records.")
        return 0 if count > 0 else 1
    except Exception as e:
        print(f"[ERROR] Export failed: {e}")
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
