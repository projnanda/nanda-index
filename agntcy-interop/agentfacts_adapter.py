"""AgentFacts adapter and validation utilities.

Converts between Nanda registry agent entries and AgentFacts schema-compliant
JSON records, and performs JSON Schema validation.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Tuple, Optional

from jsonschema import Draft7Validator

SCHEMA_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'agentfacts-format', 'agentfacts_schema.json'))

class SchemaLoadError(RuntimeError):
    pass

try:
    # Import SkillMapper from local exporter for taxonomy-based mapping if available
    from .export_nanda_to_agntcy import SkillMapper, DEFAULT_OASF_SCHEMA_DIR
except Exception:  # pragma: no cover
    SkillMapper = None  # type: ignore
    DEFAULT_OASF_SCHEMA_DIR = "../agntcy/oasf/schema"


class AgentFactsAdapter:
    _validator: Draft7Validator | None = None
    _schema: Dict[str, Any] | None = None

    def __init__(self, schema_path: str = SCHEMA_PATH, skill_mapper: Optional[SkillMapper] = None):
        self.schema_path = schema_path
        if AgentFactsAdapter._schema is None:
            AgentFactsAdapter._schema = self._load_schema(schema_path)
        if AgentFactsAdapter._validator is None:
            AgentFactsAdapter._validator = Draft7Validator(AgentFactsAdapter._schema)
        # Initialize taxonomy skill mapper if provided or auto-detected
        self.skill_mapper = skill_mapper
        if self.skill_mapper is None and SkillMapper is not None:
            from pathlib import Path
            schema_dir = Path(DEFAULT_OASF_SCHEMA_DIR)
            if schema_dir.exists():  # Only build if taxonomy present
                try:
                    self.skill_mapper = SkillMapper(schema_dir)
                except Exception:
                    self.skill_mapper = None  # Non-fatal

    def _load_schema(self, path: str) -> Dict[str, Any]:
        if not os.path.exists(path):
            raise SchemaLoadError(f"AgentFacts schema not found at {path}")
        with open(path, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError as e:
                raise SchemaLoadError(f"Invalid JSON in schema file {path}: {e}") from e

    # ---------------- Validation -----------------
    def validate_record(self, record: Dict[str, Any]) -> Tuple[bool, List[Dict[str, Any]]]:
        """Validate an AgentFacts record against the schema.

        Returns (is_valid, errors). Each error is a dict: {path, message, validator, value}.
        """
        validator = AgentFactsAdapter._validator
        errors: List[Dict[str, Any]] = []
        if validator is None:
            raise SchemaLoadError("Validator not initialized")
        for err in sorted(validator.iter_errors(record), key=lambda e: e.path):
            path = list(err.absolute_path)
            errors.append({
                'path': path,
                'message': err.message,
                'validator': err.validator,
                'value': err.instance,
            })
        return (len(errors) == 0, errors)

    # ---------------- Conversion -----------------
    def registry_to_record(self, agent: Dict[str, Any]) -> Dict[str, Any]:
        """Convert a Nanda registry agent entry into an AgentFacts record.

        Expected agent fields (flexible): id / agent_name, label/name, description,
        version, provider info, endpoints list or str, capabilities list.
        """
        # Basic identity mapping with safe fallbacks.
        agent_id = agent.get('id') or agent.get('agent_id') or agent.get('name')
        label = agent.get('label') or agent.get('name') or agent_id
        description = agent.get('description') or agent.get('caption') or ''
        version = str(agent.get('version') or '1.0.0')

        provider = agent.get('provider') or {}
        if isinstance(provider, str):
            provider = {'name': provider, 'url': agent.get('provider_url', 'https://example.com')}
        provider.setdefault('name', label)
        provider.setdefault('url', 'https://example.com')

        # Endpoints: agent may store endpoint(s) under various keys.
        raw_endpoints = agent.get('endpoints') or agent.get('endpoint') or []
        if isinstance(raw_endpoints, str):
            static_endpoints = [raw_endpoints]
        elif isinstance(raw_endpoints, list):
            static_endpoints = [e for e in raw_endpoints if isinstance(e, str)]
        else:
            static_endpoints = []
        endpoints = {'static': static_endpoints}

        # Capabilities: expect list of strings or richer objects.
        raw_caps = agent.get('capabilities') or []
        modalities: List[str] = []
        for c in raw_caps:
            if isinstance(c, str):
                modalities.append(c)
            elif isinstance(c, dict):
                # Support object with 'name' or 'id'
                name = c.get('name') or c.get('id')
                if name:
                    modalities.append(str(name))
        # Basic capability structure required by schema.
        capabilities_obj = {
            'modalities': modalities or ['text'],  # fallback modality
            'authentication': {
                'methods': ['none']
            }
        }

        # Skills: map capabilities via taxonomy SkillMapper if available; fallback to placeholders.
        skills: List[Dict[str, Any]] = []
        if self.skill_mapper:
            seen = set()
            for cap in modalities or ['text']:
                mapped = self.skill_mapper.map_capability(cap)
                if mapped and mapped['skill_id'] not in seen:
                    # Convert exporter mapping payload to AgentFacts skill shape
                    skills.append({
                        'id': mapped['skill_id'],
                        'description': f"Skill mapped from capability '{cap}' (class: {mapped.get('class_name')})",
                        'inputModes': ['text'],  # Could derive from taxonomy later
                        'outputModes': ['text']
                    })
                    seen.add(mapped['skill_id'])
        if not skills:
            # Fallback placeholder conversion
            for m in modalities or ['text']:
                skills.append({
                    'id': f"skill:{m}",
                    'description': f"Capability skill for {m}",
                    'inputModes': ['text'],
                    'outputModes': ['text']
                })
            if not skills:
                skills = [{
                    'id': 'skill:placeholder',
                    'description': 'Placeholder skill',
                    'inputModes': ['text'],
                    'outputModes': ['text']
                }]

        record: Dict[str, Any] = {
            'id': str(agent_id),
            'agent_name': str(agent_id),
            'label': str(label),
            'description': str(description),
            'version': version,
            'provider': provider,
            'endpoints': endpoints,
            'capabilities': capabilities_obj,
            'skills': skills,
        }
        return record

    def record_to_registry(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Convert AgentFacts record into minimal Nanda registry entry shape.

        Note: This is a lossy conversion until registry supports richer fields.
        """
        agent_id = record.get('id') or record.get('agent_name')
        capabilities = record.get('capabilities', {})
        modalities = capabilities.get('modalities', [])
        # Flatten endpoints static list.
        endpoints_obj = record.get('endpoints', {})
        endpoints = endpoints_obj.get('static', []) if isinstance(endpoints_obj, dict) else []
        return {
            'id': agent_id,
            'name': record.get('label') or agent_id,
            'description': record.get('description', ''),
            'version': record.get('version', '1.0.0'),
            'capabilities': modalities,
            'endpoints': endpoints,
        }

# Convenience singleton accessor
_adapter_instance: AgentFactsAdapter | None = None

def get_adapter() -> AgentFactsAdapter:
    global _adapter_instance
    if _adapter_instance is None:
        _adapter_instance = AgentFactsAdapter()
    return _adapter_instance

__all__ = [
    'AgentFactsAdapter',
    'get_adapter',
    'SchemaLoadError'
]
