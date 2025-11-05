"""Tests for AgentFacts adapter validation and conversion."""

import importlib.util
import pathlib

# Attempt dynamic import of agentfacts_adapter without relying on package name resolution
_adapter_path = pathlib.Path(__file__).parent.parent / 'agentfacts_adapter.py'
_spec = importlib.util.spec_from_file_location('agentfacts_adapter', str(_adapter_path))
assert _spec is not None and _spec.loader is not None, 'Failed to create spec for agentfacts_adapter'
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)  # type: ignore[attr-defined]
get_adapter = _module.get_adapter


def test_registry_to_record_minimal_valid():
    adapter = get_adapter()
    agent = {
        'id': 'agent-123',
        'name': 'ExampleAgent',
        'description': 'Does example things',
        'capabilities': ['text', 'math'],
        'endpoints': ['https://api.example.com/v1/invoke']
    }
    record = adapter.registry_to_record(agent)
    is_valid, errors = adapter.validate_record(record)
    assert is_valid, f"Record should be valid but errors: {errors}"\


def test_validate_missing_required_field():
    adapter = get_adapter()
    agent = {
        'id': 'agent-456',
        'name': 'BrokenAgent',
        'capabilities': ['text'],
        'endpoints': ['https://api.example.com/v1/run']
    }
    record = adapter.registry_to_record(agent)
    # Remove a required skill field to force validation error.
    record['skills'][0].pop('inputModes', None)
    is_valid, errors = adapter.validate_record(record)
    assert not is_valid
    # Ensure at least one error references the missing inputModes path.
    # Missing required property will yield an error with validator 'required' at parent path
    assert any(e['validator'] == 'required' and e['path'] == ['skills', 0] for e in errors), errors


def test_validate_negative_latency():
    adapter = get_adapter()
    agent = {
        'id': 'agent-789',
        'name': 'LatencyAgent',
        'description': 'Tests latency budget negative',
        'capabilities': ['text'],
        'endpoints': ['https://api.example.com/v1/invoke']
    }
    record = adapter.registry_to_record(agent)
    # Inject latencyBudgetMs negative into first skill
    record['skills'][0]['latencyBudgetMs'] = -5
    is_valid, errors = adapter.validate_record(record)
    assert not is_valid
    assert any(e['validator'] == 'minimum' for e in errors)


def test_round_trip_record_to_registry():
    adapter = get_adapter()
    agent = {
        'id': 'agent-999',
        'name': 'RoundTrip',
        'description': 'For round-trip test',
        'capabilities': ['text'],
        'endpoints': ['https://api.example.com/v1/invoke']
    }
    record = adapter.registry_to_record(agent)
    back = adapter.record_to_registry(record)
    assert back['id'] == agent['id']
    assert 'text' in back['capabilities']
    assert back['endpoints'] == agent['endpoints']
