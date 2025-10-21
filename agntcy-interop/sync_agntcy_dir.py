#!/usr/bin/env python3
"""Sync AGNTCY directory record JSON files into Nanda Index registry.

Maps each *.record.json to a registration payload:
  agent_id = "{name}:{version}" (slashes in name replaced with '-')
  agent_url = first locator URL (if present) else placeholder
  api_url  = optional; if an extension with name containing 'runtime/mcp' exists, create a pseudo docker run hint

Usage:
  python sync_agntcy_dir.py --records-path ../agntcy/dir/docs/research/integrations --registry-url http://localhost:6900 --limit 10

Flags:
  --records-path    Root directory to scan for *.record.json (recursive)
  --registry-url    Base URL of registry (default http://localhost:6900)
  --dry-run         Do not perform POST; just print planned registrations
  --limit           Maximum number of records to process (optional)

Exit Codes:
  0 success; >0 on errors.
"""
import argparse
import json
import sys
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
import requests

DEFAULT_REGISTRY_URL = os.environ.get("REGISTRY_URL", "http://localhost:6900")


def find_record_files(root: Path) -> List[Path]:
    return list(root.rglob("*.record.json"))


def parse_record(path: Path) -> Optional[Dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[WARN] Failed to parse {path}: {e}")
        return None


def derive_agent_fields(record: Dict[str, Any]) -> Dict[str, Any]:
    name = record.get("name") or "unnamed"
    version = record.get("version") or "v0"
    agent_id = f"{name}:{version}".replace("/", "-")

    # Locators
    locators = record.get("locators", [])
    agent_url = None
    if locators:
        # Prioritize docker-image then fallback to first locator
        docker = next((locator_item for locator_item in locators if locator_item.get("type") == "docker-image"), None)
        agent_url = (docker or locators[0]).get("url")
    if not agent_url:
        agent_url = f"placeholder://{agent_id}"  # Fallback placeholder

    # api_url heuristic: look into extensions runtime/mcp for a server command
    api_url = None
    for ext in record.get("extensions", []):
        if "runtime/mcp" in ext.get("name", ""):
            data = ext.get("data", {})
            servers = data.get("servers", {})
            # Pick first server definition to construct a pseudo command descriptor as api_url
            for _, server_cfg in servers.items():
                command = server_cfg.get("command")
                args = server_cfg.get("args", [])
                if command:
                    api_url = f"cmd://{command}?args={' '.join(args)}"
                    break
            if api_url:
                break

    return {
        "agent_id": agent_id,
        "agent_url": agent_url,
        "api_url": api_url,
    }


def register_agent(registry_url: str, payload: Dict[str, Any]) -> bool:
    try:
        resp = requests.post(f"{registry_url}/register", json=payload, timeout=10)
        if resp.status_code == 200:
            print(f"[OK] Registered {payload['agent_id']}")
            return True
        else:
            print(f"[ERR] Failed {payload['agent_id']} status={resp.status_code} body={resp.text}")
            return False
    except Exception as e:
        print(f"[ERR] Exception registering {payload['agent_id']}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Sync AGNTCY directory records into Nanda Index registry")
    parser.add_argument("--records-path", required=True, help="Root directory containing *.record.json files")
    parser.add_argument("--registry-url", default=DEFAULT_REGISTRY_URL, help="Base URL of registry")
    parser.add_argument("--dry-run", action="store_true", help="Only print actions without executing")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of records to process")
    args = parser.parse_args()

    root = Path(args.records_path)
    if not root.exists():
        print(f"[ERROR] Path does not exist: {root}")
        return 2

    files = find_record_files(root)
    if args.limit is not None:
        files = files[:args.limit]

    if not files:
        print("[INFO] No record files found.")
        return 0

    print(f"[INFO] Found {len(files)} record files under {root}")

    success = 0
    for path in files:
        record = parse_record(path)
        if not record:
            continue
        payload = derive_agent_fields(record)
        if args.dry_run:
            print(f"[DRY] Would register: {payload}")
            continue
        if register_agent(args.registry_url, payload):
            success += 1

    print(f"[SUMMARY] Registered {success} agents out of {len(files)} processed.")
    return 0 if success > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
