"""Comparison failures retain per-case evidence and are visible to MCP callers."""
import hashlib
import json

import pytest

from polya import find, run
from polya import symbolic
from polya.mcp_server import Server
from polya.native_z3 import BackendUnavailable, UnsupportedModel


def invoke(inputs, version='2025-06-18'):
    server = Server()
    server.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',
                   'params': {'protocolVersion': version}})
    server.handle({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
    response = server.handle({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call',
        'params': {'name': 'puzzle.run', 'arguments': {
            'operation_id': 'hypotheses.compare', 'inputs': inputs}}})['result']
    return response, json.loads(response['content'][0]['text'])


def inputs(**overrides):
    return {'model': {'variables': {'x': {'values': [0, 1]}}},
            'cases': {'a': [], 'b': []}, 'backend': 'reference', **overrides}


@pytest.mark.parametrize('version', ['2025-06-18', '2025-03-26', '2024-11-05'])
@pytest.mark.parametrize(('failure', 'status'), [
    (BackendUnavailable, 'UNAVAILABLE'), (UnsupportedModel, 'UNSUPPORTED'),
])
def test_comparison_backend_failures_flag_mcp_without_losing_receipts(monkeypatch, version, failure, status):
    def fail(*args):
        raise failure('synthetic backend failure')
    monkeypatch.setattr(symbolic, 'Z3Engine', fail)
    response, payload = invoke(inputs(backend='z3'), version)
    assert response['isError'] is True
    assert payload['execution_error']['code'] == 'EXECUTION_ERROR'
    assert 'backends.inspect' in payload['execution_error']['recovery']
    data = payload['data']
    result = data['result']
    assert result['status'] == 'EXECUTION_ERROR' and result['complete'] is False
    assert result['failed_cases'] == {'a': status, 'b': status}
    assert result['distinguishing_observations'] == []
    assert all(case['status'] == status and case['stats']['solver_checks'] == 0
               for case in result['cases'].values())
    encoded = json.dumps(result, ensure_ascii=True, sort_keys=True, separators=(',', ':'), allow_nan=False)
    assert data['receipt']['result_sha256'] == hashlib.sha256(encoded.encode()).hexdigest()
    assert data['receipt']['operation_version'] == '3'
    if version == '2025-06-18':
        assert response['structuredContent'] == payload


def test_comparison_keeps_successful_case_when_another_is_unsupported(monkeypatch):
    def selective_backend(model, active, budget):
        if any(rule.id == 'unsupported' for rule in active):
            raise UnsupportedModel('synthetic unsupported hypothesis')
        return symbolic.ReferenceEngine(model, active, budget)
    monkeypatch.setattr(symbolic, 'Z3Engine', selective_backend)
    request = inputs(model={'variables': {'x': {'values': [0, 1]}}, 'constraints': [
        {'id': 'zero', 'kind': 'hypothesis', 'expr': {'op': 'eq', 'args': ['x', 0]}},
        {'id': 'one', 'kind': 'hypothesis', 'expr': {'op': 'eq', 'args': ['x', 1]}},
        {'id': 'unsupported', 'kind': 'hypothesis', 'expr': True},
    ]}, cases={'a': ['zero'], 'b': ['one'], 'c': ['unsupported']}, backend='z3')
    response, payload = invoke(request)
    result = payload['data']['result']
    assert response['isError'] is True
    assert result['status'] == 'EXECUTION_ERROR' and result['failed_cases'] == {'c': 'UNSUPPORTED'}
    assert result['cases']['a']['forced_values'] == {'x': 0}
    assert result['cases']['a']['complete'] is True
    assert result['cases']['b']['forced_values'] == {'x': 1}
    assert result['cases']['c']['status'] == 'UNSUPPORTED'
    assert result['complete'] is False
    assert result['distinguishing_observations'] == [
        {'variable': 'x', 'predictions': {'a': 0, 'b': 1}, 'observation_acquired': False}]


def test_real_cpsat_bitvector_comparison_reports_unsupported():
    # Import startup is outside the comparison budget, as in the deployed server.
    pytest.importorskip('ortools.sat.python.cp_model')
    response, payload = invoke(inputs(
        model={'variables': {'x': {'kind': 'bitvec', 'width': 2, 'values': [0, 1]}}},
        backend='cpsat'))
    result = payload['data']['result']
    assert response['isError'] is True
    assert result['failed_cases'] == {'a': 'UNSUPPORTED', 'b': 'UNSUPPORTED'}
    assert all(case['status'] == 'UNSUPPORTED' for case in result['cases'].values())


def test_completed_comparison_preserves_exact_reference_predictions():
    request = inputs(model={'variables': {'x': {'values': [0, 1]}}, 'constraints': [
        {'id': 'zero', 'kind': 'hypothesis', 'expr': {'op': 'eq', 'args': ['x', 0]}},
        {'id': 'one', 'kind': 'hypothesis', 'expr': {'op': 'eq', 'args': ['x', 1]}},
    ]}, cases={'a': ['zero'], 'b': ['one']})
    response, payload = invoke(request)
    result = payload['data']['result']
    assert response['isError'] is False and 'execution_error' not in payload
    assert result['status'] == 'COMPLETE' and result['complete'] is True
    assert result['failed_cases'] == {}
    assert result['distinguishing_observations'] == [
        {'variable': 'x', 'predictions': {'a': 0, 'b': 1}, 'observation_acquired': False}]


def test_completed_unsat_comparison_is_not_an_execution_error():
    response, payload = invoke(inputs(model={'variables': {'x': {'values': []}}}))
    result = payload['data']['result']
    assert response['isError'] is False and 'execution_error' not in payload
    assert result['status'] == 'COMPLETE' and result['complete'] is True
    assert result['failed_cases'] == {}
    assert all(case['status'] == 'UNSAT' for case in result['cases'].values())


def test_shared_budget_unknown_is_partial_not_an_execution_error():
    response, payload = invoke(inputs(max_checks=1))
    result = payload['data']['result']
    assert response['isError'] is False and 'execution_error' not in payload
    assert result['status'] == 'PARTIAL' and result['complete'] is False
    assert result['failed_cases'] == {}
    assert result['cases']['b']['status'] == 'UNKNOWN'
    assert result['cases']['b']['reason'] == 'shared_budget'


def test_contract_declares_comparison_failure_and_malformed_input_still_rejects():
    contract = find(operation_id='hypotheses.compare')
    assert contract['version'] == '3'
    assert contract['execution_error_statuses'] == ['EXECUTION_ERROR']
    assert 'failed_cases' in contract['output_schema']['required']
    with pytest.raises(ValueError):
        run('hypotheses.compare', inputs(cases={'only_one': []}))
