"""Discovery ownership and MCP execution failures are separate from puzzle outcomes."""
from copy import deepcopy
from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from polya import find, run
from polya.catalog import REGISTRY
from polya.mcp_server import Server


def ready(version='2025-06-18'):
    server = Server()
    server.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': version}})
    server.handle({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
    return server


def invoke(server, oid, inputs):
    return server.handle({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call',
                          'params': {'name': 'puzzle.run', 'arguments': {'operation_id': oid, 'inputs': inputs}}})['result']


def test_contract_example_is_a_deep_owned_copy():
    expected = deepcopy(REGISTRY['constraints.solve'].example)
    contract = find(operation_id='constraints.solve')
    contract['example']['domains']['a'].append('changed')
    contract['example']['constraints'][0]['allowed'][0][0] = 'also changed'
    assert find(operation_id='constraints.solve')['example'] == expected
    assert REGISTRY['constraints.solve'].example == expected
    assert find(operation_id='backends.inspect')['example'] is None


@pytest.mark.parametrize('version', ['2025-06-18', '2025-03-26', '2024-11-05'])
@pytest.mark.parametrize('status', ['UNAVAILABLE', 'VERSION_MISMATCH', 'TIMEOUT', 'PROTOCOL_ERROR', 'UPSTREAM_ERROR'])
def test_jacobian_failure_has_transport_flag_and_preserves_receipt(monkeypatch, version, status):
    # Use the genuine bridge result schema, not a generic fake error envelope.
    monkeypatch.setenv('POLYA_JACOBIAN_MCP', '/definitely-absent/polya-test-jacobian')
    result = run('jacobian.find', {'query': 'gcd'})['result']
    result['status'] = status
    op = REGISTRY['jacobian.find']
    monkeypatch.setitem(REGISTRY, 'jacobian.find', replace(op, kernel=lambda **kwargs: result))
    response = invoke(ready(version), 'jacobian.find', {'query': 'gcd'})
    payload = json.loads(response['content'][0]['text'])
    assert response['isError'] is True
    assert payload['execution_error']['code'] == status
    assert payload['execution_error']['recovery']
    assert payload['data']['result']['status'] == status
    assert payload['data']['receipt']['result_sha256']
    if version == '2025-06-18':
        assert response['structuredContent'] == payload


@pytest.mark.parametrize('inputs', [
    {'model': {'variables': {'x': {'values': []}}}, 'backend': 'reference'},
    {'model': {'variables': {'x': {'values': [0, 1]}}}, 'backend': 'reference', 'max_checks': 1},
])
def test_valid_unsat_and_budget_outcomes_are_not_mcp_errors(inputs):
    response = invoke(ready(), 'symbolic.solve', inputs)
    assert not response['isError']
    assert response['structuredContent']['data']['result']['status'] in ('UNSAT', 'SAT', 'UNKNOWN')
    assert 'execution_error' not in response['structuredContent']


def test_missing_backend_discovery_is_successful_inspection(monkeypatch):
    monkeypatch.setenv('POLYA_JACOBIAN_MCP', '/definitely-absent/polya-test-jacobian')
    response = invoke(ready(), 'jacobian.inspect', {})
    assert not response['isError']
    assert response['structuredContent']['data']['result']['executable_found'] is False


def test_target_negative_and_failed_preflight_are_successful_diagnostics():
    response = invoke(ready(), 'verify.sha256', {'candidate_hex': '00', 'expected_sha256': '0' * 64})
    assert not response['isError'] and response['structuredContent']['data']['result']['match'] is False
    response = invoke(ready(), 'mechanism.plan_inspect', {'plan': {}})
    assert not response['isError'] and response['structuredContent']['data']['result']['valid'] is False


def test_real_stdio_missing_jacobian_is_flagged():
    messages = [
        {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2025-06-18'}},
        {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
        {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {'name': 'puzzle.run',
         'arguments': {'operation_id': 'jacobian.find', 'inputs': {'query': 'gcd'}}}},
    ]
    env = {**os.environ, 'POLYA_JACOBIAN_MCP': str(Path.cwd() / 'not-a-jacobian-executable')}
    completed = subprocess.run([sys.executable, '-m', 'polya', 'mcp'],
        input=''.join(json.dumps(m) + '\n' for m in messages), text=True, capture_output=True, timeout=15, env=env)
    assert completed.returncode == 0, completed.stderr
    response = json.loads(completed.stdout.splitlines()[-1])['result']
    assert response['isError']
    assert response['structuredContent']['execution_error']['code'] == 'UNAVAILABLE'
