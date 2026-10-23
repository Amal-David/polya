"""Later operational failures retain checked witnesses and explicit proof gaps."""
import json

import pytest

from polya import run
from polya import symbolic
from polya.mcp_server import Server
from polya.native_z3 import BackendUnavailable, UnsupportedModel


MODEL = {'variables': {'x': {'values': [0, 1]}}}


def rpc(operation_id, inputs):
    server = Server()
    server.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',
                   'params': {'protocolVersion': '2025-06-18'}})
    server.handle({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
    return server.handle({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call',
                          'params': {'name': 'puzzle.run', 'arguments': {
                              'operation_id': operation_id, 'inputs': inputs}}})['result']


@pytest.mark.parametrize('failure,status', [(UnsupportedModel, 'UNSUPPORTED'),
                                           (BackendUnavailable, 'UNAVAILABLE')])
def test_late_uniqueness_failure_preserves_sat_witness_and_proof_gap(monkeypatch, failure, status):
    class LaterFailure(symbolic.ReferenceEngine):
        def check(self, extra):
            if not extra:
                return super().check(extra)
            if self.budget.begin_check() is None:
                return {'status': 'UNKNOWN', 'reason': self.budget.reason}
            raise failure('synthetic late failure')

    monkeypatch.setattr(symbolic, 'Z3Engine', LaterFailure)
    response = rpc('symbolic.analyze', {'model': MODEL, 'backend': 'z3'})
    data = response['structuredContent']['data']
    result = data['result']
    assert response['isError'] is True
    assert response['structuredContent']['execution_error']['code'] == 'EXECUTION_ERROR'
    assert result['status'] == 'SAT' and result['assignment'] == {'x': 0}
    assert result['uniqueness'] == 'UNKNOWN' and not result['complete']
    assert result['execution_status'] == 'EXECUTION_ERROR'
    assert result['forced_values'] == {} and result['undetermined'] == ['x']
    assert result['failed_checks'] == [
        {'phase': 'uniqueness', 'variable': None, 'status': status, 'reason': 'synthetic late failure'},
        {'phase': 'forced_value', 'variable': 'x', 'status': status, 'reason': 'synthetic late failure'}]
    assert result['stats']['solver_checks'] == 3
    assert data['receipt']['operation_version'] == '2'

    comparison = rpc('hypotheses.compare', {
        'model': MODEL, 'cases': {'a': [], 'b': []}, 'backend': 'z3'})
    result = comparison['structuredContent']['data']['result']
    assert comparison['isError'] is True and result['status'] == 'EXECUTION_ERROR'
    assert result['failed_cases'] == {'a': status, 'b': status}
    assert all(case['status'] == 'SAT' and case['assignment'] == {'x': 0}
               and not case['complete'] for case in result['cases'].values())


def test_forced_value_failure_does_not_discard_valid_alternative(monkeypatch):
    class ForcedFailure(symbolic.ReferenceEngine):
        def check(self, extra):
            # The single-variable blocking check is later than the full projected
            # alternative, which still establishes MULTIPLE exactly.
            if extra and len(extra[0]['args']) == 1:
                self.budget.begin_check()
                raise UnsupportedModel('synthetic forced-value limitation')
            return super().check(extra)

    monkeypatch.setattr(symbolic, 'Z3Engine', ForcedFailure)
    model = {'variables': {'x': {'values': [0]}, 'y': {'values': [0, 1]}}}
    result = run('symbolic.analyze', {'model': model, 'backend': 'z3'})['result']
    assert result['status'] == 'SAT' and result['uniqueness'] == 'MULTIPLE'
    assert result['assignment'] == {'x': 0, 'y': 0}
    assert result['alternative_assignment'] == {'x': 0, 'y': 1}
    assert result['not_forced'] == ['y'] and result['undetermined'] == ['x']
    assert result['execution_status'] == 'EXECUTION_ERROR' and not result['complete']
    assert result['failed_checks'] == [
        {'phase': 'forced_value', 'variable': 'x', 'status': 'UNSUPPORTED',
         'reason': 'synthetic forced-value limitation'}]


def test_late_enumeration_failure_preserves_verified_answers(monkeypatch):
    class LaterFailure(symbolic.ReferenceEngine):
        def check(self, extra):
            if extra:
                self.budget.begin_check()
                raise UnsupportedModel('synthetic enumeration limitation')
            return super().check(extra)

    monkeypatch.setattr(symbolic, 'Z3Engine', LaterFailure)
    response = rpc('symbolic.solve', {'model': MODEL, 'backend': 'z3'})
    result = response['structuredContent']['data']['result']
    assert response['isError'] is True
    assert result['status'] == 'SAT' and result['solutions'] == [{'x': 0}]
    assert result['witnesses'] == [{'x': 0}] and not result['complete']
    assert result['execution_status'] == 'EXECUTION_ERROR'
    assert result['failed_checks'][0]['phase'] == 'enumeration'


def test_budget_exhaustion_and_complete_unsat_remain_valid_outcomes():
    for operation in ['symbolic.solve', 'symbolic.analyze']:
        response = rpc(operation, {'model': MODEL, 'backend': 'reference', 'max_checks': 1})
        result = response['structuredContent']['data']['result']
        assert response['isError'] is False and result['status'] == 'SAT'
        assert result['execution_status'] == 'PARTIAL' and result['failed_checks'] == []
        assert not result['complete'] and result['stats']['solver_checks'] == 1
        response = rpc(operation, {'model': {'variables': {'x': {'values': []}}}, 'backend': 'reference'})
        result = response['structuredContent']['data']['result']
        assert response['isError'] is False and result['status'] == 'UNSAT'
        assert result['execution_status'] == 'COMPLETE' and result['failed_checks'] == []
        assert result['complete']


def test_shared_budget_failure_does_not_run_unbudgeted_comparison_cases(monkeypatch):
    class LaterFailure(symbolic.ReferenceEngine):
        def check(self, extra):
            if extra:
                if self.budget.begin_check() is None:
                    return {'status': 'UNKNOWN', 'reason': self.budget.reason}
                raise UnsupportedModel('synthetic late failure')
            return super().check(extra)

    monkeypatch.setattr(symbolic, 'Z3Engine', LaterFailure)
    response = rpc('hypotheses.compare', {'model': MODEL, 'cases': {'a': [], 'b': []},
                                        'backend': 'z3', 'max_checks': 2})
    result = response['structuredContent']['data']['result']
    assert response['isError'] is True
    assert result['failed_cases'] == {'a': 'UNSUPPORTED'}
    assert result['cases']['a']['stats']['solver_checks'] == 2
    assert result['cases']['b']['status'] == 'UNKNOWN'
    assert result['cases']['b']['reason'] == 'shared_budget'
    assert result['cases']['b']['failed_checks'] == []


def test_inspection_mcp_diagnostics_and_explicit_normalized_execution():
    invalid = rpc('symbolic.inspect', {'model': {'variables': {'x': {}}}})
    assert invalid['isError'] is False
    result = invalid['structuredContent']['data']['result']
    assert result['status'] == 'INVALID' and not result['valid']
    assert result['diagnostics'][0]['path'] == ['model', 'variables', 'x']
    raw = {'variables': {'x': {'lower': -3, 'upper': 3}}, 'constraints': [
        {'id': 'bound', 'expr': {'op': 'gt', 'args': [
            {'op': 'mul', 'args': [-4_000_000_000_000, 'x']}, 6_000_000_000_001]}}]}
    inspected = rpc('symbolic.inspect', {'model': raw, 'normalize_coefficients': True})
    assert inspected['isError'] is False
    model = inspected['structuredContent']['data']['result']['normalized_model']
    assert model['constraints'][0]['expr'] == {'op': 'le', 'args': ['x', -2]}
    answer = rpc('symbolic.solve', {'model': model, 'backend': 'reference'})
    result = answer['structuredContent']['data']['result']
    assert answer['isError'] is False and result['complete']
    assert result['solutions'] == [{'x': -3}, {'x': -2}]
    assert json.loads(answer['content'][0]['text']) == answer['structuredContent']
