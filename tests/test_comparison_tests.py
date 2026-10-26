"""A comparison becomes conditional test inputs, never an acquired observation."""
from copy import deepcopy
import hashlib
import json
import subprocess
import sys

import pytest

from polya import catalog, find, run, symbolic
from polya.mcp_server import Server
from polya.native_z3 import BackendUnavailable, UnsupportedModel


def request():
    return {'model': {'variables': {'x': {'values': [0, 1, 2]}, 'flag': {'kind': 'bool'}},
                     'constraints': [
                         {'id': 'flag-definition', 'expr': {'op': 'eq', 'args': [
                             'flag', {'op': 'eq', 'args': ['x', 0]}]}},
                         {'id': 'zero', 'kind': 'hypothesis', 'expr': {'op': 'eq', 'args': ['x', 0]}},
                         {'id': 'one', 'kind': 'hypothesis', 'expr': {'op': 'eq', 'args': ['x', 1]}},
                     ]}, 'cases': {'zero-case': ['zero'], 'one-case': ['one'], 'unconstrained': []},
            'backend': 'reference'}


def observables():
    return [{'variable': 'x', 'id': 'read-x', 'question': 'Read the numeral in the marked cell.',
             'source': 'Synthetic board, marked cell', 'cost': 1},
            {'variable': 'flag', 'id': 'read-flag', 'question': 'Is the indicator lit?',
             'source': 'Synthetic board, indicator', 'cost': 2}]


def adapt(inputs=None, comparison=None, **overrides):
    inputs = request() if inputs is None else inputs
    comparison = run('hypotheses.compare', inputs) if comparison is None else comparison
    return run('experiment.from_comparison', {
        'comparison_inputs': inputs, 'comparison': comparison,
        'observables': observables(), **overrides})['result']


def rehash_result(envelope):
    """A caller can update a hash; nested consistency must not rely on secrecy."""
    envelope['receipt']['result_sha256'] = hashlib.sha256(
        catalog.canonical_json(envelope['result']).encode()).hexdigest()


def test_predictions_match_independent_small_truth_table_and_rank_by_cost():
    inputs = request()
    comparison = run('hypotheses.compare', inputs)
    adapted = adapt(inputs, comparison)
    tests = {test['id']: test for test in adapted['rank_inputs']['tests']}
    # Independent hand-specified semantics; do not call the model evaluator.
    rows = [{'x': x, 'flag': x == 0} for x in range(3)]
    possibilities = {'zero-case': [row for row in rows if row['x'] == 0],
                     'one-case': [row for row in rows if row['x'] == 1],
                     'unconstrained': rows}
    for variable, sort in [('x', 'int'), ('flag', 'bool')]:
        predictions = tests['read-' + variable]['predictions']
        for name, candidates in possibilities.items():
            values = {json.dumps(row[variable]) for row in candidates}
            expected = sort + ':' + next(iter(values)) if len(values) == 1 else None
            assert predictions[name] == expected
    ranked = run('experiment.rank_tests', adapted['rank_inputs'])['result']
    assert ranked['next_test_id'] == 'read-x'
    assert ranked['tests'][0]['separation_numerator'] == 1
    assert ranked['tests'][0]['separation_denominator'] == 3
    assert ranked['tests'][0]['unresolved_pair_mass'] == '2/3'
    assert ranked['tests'][0]['information_bits_if_model_correct'] is None
    assert adapted['comparison_identity']['inputs_sha256'] == comparison['receipt']['inputs_sha256']
    assert adapted['comparison_identity']['result_sha256'] == comparison['receipt']['result_sha256']
    assert adapted['case_evidence']['zero-case']['requested_hypotheses'] == ['zero']
    assert adapted['observation_acquired'] is False
    assert 'not authenticated' in adapted['scope']


def test_shared_budget_preserves_unexecuted_cases_and_partial_forced_values():
    inputs = {'model': {'variables': {name: {'values': [0, 1]} for name in ('x', 'y', 'z')},
                        'constraints': [{'id': 'x-zero', 'expr': {'op': 'eq', 'args': ['x', 0]}},
                                        {'id': 'z-one', 'expr': {'op': 'eq', 'args': ['z', 1]}}]},
              'cases': {'first': [], 'unexecuted': []}, 'backend': 'reference', 'max_checks': 3}
    comparison = run('hypotheses.compare', inputs)
    first = comparison['result']['cases']['first']
    assert first['status'] == 'SAT' and first['complete'] is False
    assert first['forced_values'] == {'x': 0}
    adapted = adapt(inputs, comparison, observables=[observables()[0]])
    assert adapted['rank_inputs']['tests'][0]['predictions'] == {'first': 'int:0', 'unexecuted': None}
    assert adapted['case_evidence']['unexecuted']['status'] == 'UNKNOWN'
    assert run('experiment.rank_tests', adapted['rank_inputs'])['result']['status'] == 'NO_DISCRIMINATING_TEST'


def test_late_backend_failures_preserve_already_forced_predictions(monkeypatch):
    original = symbolic.ReferenceEngine

    class LateFailure(original):
        def __init__(self, *args):
            super().__init__(*args)
            self.calls = 0

        def check(self, extras):
            self.calls += 1
            if self.calls == 4:
                raise UnsupportedModel('synthetic failure after one forced-value proof')
            return super().check(extras)

    monkeypatch.setattr(symbolic, 'ReferenceEngine', LateFailure)
    inputs = {'model': {'variables': {name: {'values': [0, 1]} for name in ('x', 'y', 'z')},
                        'constraints': [{'id': 'x-zero', 'kind': 'hypothesis', 'expr': {'op': 'eq', 'args': ['x', 0]}},
                                        {'id': 'x-one', 'kind': 'hypothesis', 'expr': {'op': 'eq', 'args': ['x', 1]}},
                                        {'id': 'z-one', 'expr': {'op': 'eq', 'args': ['z', 1]}}]},
              'cases': {'first': ['x-zero'], 'second': ['x-one']}, 'backend': 'reference'}
    comparison = run('hypotheses.compare', inputs)
    assert comparison['result']['status'] == 'EXECUTION_ERROR'
    adapted = adapt(inputs, comparison, observables=[observables()[0]])
    assert adapted['rank_inputs']['tests'][0]['predictions'] == {'first': 'int:0', 'second': 'int:1'}
    assert all(case['execution_status'] == 'EXECUTION_ERROR' for case in adapted['case_evidence'].values())
    assert run('experiment.rank_tests', adapted['rank_inputs'])['result']['next_test_id'] == 'read-x'


def test_unavailable_and_unsat_cases_are_not_eliminated(monkeypatch):
    def unavailable(*args):
        raise BackendUnavailable('synthetic unavailable backend')

    monkeypatch.setattr(symbolic, 'Z3Engine', unavailable)
    unavailable_inputs = {**request(), 'backend': 'z3'}
    adapted = adapt(unavailable_inputs)
    assert all(case['status'] == 'UNAVAILABLE' for case in adapted['case_evidence'].values())
    assert all(value is None for test in adapted['rank_inputs']['tests'] for value in test['predictions'].values())
    inputs = request()
    inputs['cases']['contradictory'] = ['zero', 'one']
    adapted = adapt(inputs)
    assert adapted['case_evidence']['contradictory']['status'] == 'UNSAT'
    assert len(adapted['rank_inputs']['hypotheses']) == 4
    assert all(test['predictions']['contradictory'] is None for test in adapted['rank_inputs']['tests'])


def test_unsigned_bitvector_outcomes_keep_their_sort_width():
    inputs = {'model': {'variables': {'x': {'kind': 'bitvec', 'width': 2, 'values': [0, 1]}},
                        'constraints': [{'id': 'zero', 'kind': 'hypothesis',
                                         'expr': {'op': 'eq', 'args': ['x', {'bv': 0, 'width': 2}]}},
                                        {'id': 'one', 'kind': 'hypothesis',
                                         'expr': {'op': 'eq', 'args': ['x', {'bv': 1, 'width': 2}]}}]},
              'cases': {'a': ['zero'], 'b': ['one']}, 'backend': 'reference'}
    adapted = adapt(inputs, observables=[observables()[0]])
    assert adapted['rank_inputs']['tests'][0]['predictions'] == {'a': 'bv2:0', 'b': 'bv2:1'}


@pytest.mark.parametrize(('backend', 'dependency'), [('z3', 'z3'), ('cpsat', 'ortools')])
def test_optional_solver_comparisons_produce_the_same_conditional_matrix(backend, dependency):
    pytest.importorskip(dependency)
    reference = adapt()['rank_inputs']['tests']
    adapted = adapt({**request(), 'backend': backend})
    assert adapted['rank_inputs']['tests'] == reference


def test_unsat_cannot_claim_unknown_uniqueness_in_a_rehashed_envelope():
    inputs = request()
    inputs['cases']['contradictory'] = ['zero', 'one']
    comparison = run('hypotheses.compare', inputs)
    comparison['result']['cases']['contradictory']['uniqueness'] = 'UNKNOWN'
    rehash_result(comparison)
    with pytest.raises(ValueError, match='non-SAT'):
        adapt(inputs, comparison)


@pytest.mark.parametrize('field', ['operation_version', 'inputs_sha256', 'result_sha256', 'experiment_key'])
def test_inconsistent_receipt_fields_reject(field):
    inputs = request()
    comparison = run('hypotheses.compare', inputs)
    comparison['receipt'][field] = 'wrong'
    with pytest.raises(ValueError, match='receipt'):
        adapt(inputs, comparison)


def test_other_request_cannot_reuse_comparison_even_with_same_case_names():
    inputs = request()
    comparison = run('hypotheses.compare', inputs)
    inputs['cases']['zero-case'] = ['one']
    with pytest.raises(ValueError, match='receipt'):
        adapt(inputs, comparison)


@pytest.mark.parametrize(('mutation', 'error'), [
    (lambda result: result['cases']['zero-case']['forced_values'].update(x=True), 'sort or domain'),
    (lambda result: result['cases']['zero-case']['forced_values'].update(x='0'), 'sort or domain'),
    (lambda result: result['cases']['zero-case']['forced_values'].update(x=1), 'contradict'),
    (lambda result: result['cases']['zero-case']['assignment'].update(x=1), 'verification'),
    (lambda result: result['cases']['zero-case'].update(enabled_hypotheses=['one']), 'hypotheses'),
    (lambda result: result['cases']['zero-case'].update(active_constraint_ids=[]), 'constraints'),
    (lambda result: result['cases']['zero-case'].update(uniqueness='UNSAT'), 'uniqueness'),
    (lambda result: result['cases']['zero-case'].update(uniqueness='UNKNOWN'), 'completeness'),
    (lambda result: result['cases'].pop('one-case'), 'case IDs'),
    (lambda result: result.update(status='PARTIAL'), 'aggregate status'),
    (lambda result: result['distinguishing_observations'][0]['predictions'].update(**{'zero-case': 2}), 'pair predictions'),
    (lambda result: result['distinguishing_observations'][0].update(observation_acquired=True), 'pair predictions'),
    (lambda result: result['distinguishing_observations'].append(deepcopy(result['distinguishing_observations'][0])), 'pair predictions'),
    (lambda result: result['cases']['zero-case']['stats'].update(solver_checks=10001), 'shared request budget'),
])
def test_rehashed_inconsistent_case_claims_reject(mutation, error):
    inputs = request()
    comparison = run('hypotheses.compare', inputs)
    mutation(comparison['result'])
    rehash_result(comparison)
    with pytest.raises(ValueError, match=error):
        adapt(inputs, comparison)


def test_shared_budget_cannot_be_promoted_to_a_prediction():
    inputs = {**request(), 'max_checks': 1}
    comparison = run('hypotheses.compare', inputs)
    comparison['result']['cases']['one-case']['forced_values'] = {'x': 1}
    rehash_result(comparison)
    with pytest.raises(ValueError, match='shared-budget'):
        adapt(inputs, comparison)


@pytest.mark.parametrize('observations', [
    [], observables() * 65,
    [observables()[0], observables()[0]],
    [{**observables()[0], 'cost': 0}],
    [{**observables()[0], 'cost': True}],
    [{**observables()[0], 'source': ''}],
    [{**observables()[0], 'variable': 'undeclared'}],
])
def test_observable_contract_rejects_missing_ambiguous_or_unbounded_inputs(observations):
    with pytest.raises(ValueError):
        adapt(observables=observations)


def test_case_ids_are_never_silently_truncated_for_ranking():
    inputs = request()
    inputs['cases']['a' * 65] = inputs['cases'].pop('zero-case')
    with pytest.raises(ValueError, match='1-64'):
        adapt(inputs)


def test_projection_must_include_the_observable():
    inputs = request()
    inputs['model']['answer_variables'] = ['x']
    with pytest.raises(ValueError, match='answer projection'):
        adapt(inputs)


def test_adapter_accepts_canonical_object_order_and_known_host_metadata():
    inputs = request()
    comparison = run('hypotheses.compare', inputs)
    # Canonical serialization sorts dictionaries, but not the pair-result list.
    comparison = json.loads(catalog.canonical_json(comparison))
    comparison.update(ledger_event_id='host-event', request_ref='sha256:' + '1' * 64,
                      response_ref='sha256:' + '2' * 64)
    assert adapt(inputs, comparison)['rank_inputs']['tests'][0]['predictions']['zero-case'] == 'int:0'
    comparison['unexpected_trusted_claim'] = True
    with pytest.raises(ValueError):
        adapt(inputs, comparison)


def test_historical_fingerprint_consistency_does_not_rerun_the_solver(monkeypatch):
    inputs = request()
    comparison = run('hypotheses.compare', inputs)
    op, normalized, identity, _ = catalog.prepare('hypotheses.compare', inputs)
    identity['implementation'] = 'f' * 64
    key = hashlib.sha256(catalog.canonical_json(identity).encode()).hexdigest()
    comparison['receipt'] = catalog.make_receipt(op, normalized, identity, key, comparison['result'])

    def do_not_solve(*args, **kwargs):
        raise AssertionError('the adapter must not execute a solver')

    monkeypatch.setattr(symbolic, 'ReferenceEngine', do_not_solve)
    adapted = adapt(inputs, comparison)
    assert adapted['comparison_identity']['implementation_fingerprint'] == 'f' * 64
    assert 'forced-value proofs are not re-executed' in adapted['scope']


def test_input_payload_admission_limit_also_applies_to_direct_helper():
    from polya.experiment_design import from_comparison

    inputs = request()
    comparison = run('hypotheses.compare', inputs)
    comparison['result']['scope'] = 'x' * 1_000_001
    with pytest.raises(ValueError, match='1 MB'):
        from_comparison(inputs, comparison, observables())


def test_python_cli_and_mcp_share_the_registered_contract():
    inputs = request()
    payload = {'comparison_inputs': inputs, 'comparison': run('hypotheses.compare', inputs),
               'observables': observables()}
    expected = run('experiment.from_comparison', payload)['result']
    assert find(operation_id='experiment.from_comparison')['version'] == '1'
    completed = subprocess.run([sys.executable, '-m', 'polya', 'run', 'experiment.from_comparison',
                                '--json', json.dumps(payload), '--result-only'],
                               capture_output=True, text=True, timeout=30, check=True)
    assert json.loads(completed.stdout) == expected
    server = Server()
    server.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',
                   'params': {'protocolVersion': '2025-06-18'}})
    server.handle({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
    response = server.handle({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call',
                              'params': {'name': 'puzzle.run', 'arguments': {
                                  'operation_id': 'experiment.from_comparison', 'inputs': payload}}})['result']
    assert response['isError'] is False
    assert response['structuredContent']['data']['result'] == expected
