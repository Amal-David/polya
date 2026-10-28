"""Independent completion checks for bounded finite-trace explanations."""
from copy import deepcopy
from itertools import product
import json
import random
import subprocess
import sys

import pytest

from polya import catalog, find, run
from polya.trace_explanations import Input, _evaluate


def request():
    return deepcopy(catalog.REGISTRY['trace.explain'].example)


def execute(inputs):
    return run('trace.explain', inputs)['result']


def oracle(nodes, alphabet, trace, node=None, step=0):
    """Quantified recursive semantics, independent of production recurrence."""
    node = len(nodes) - 1 if node is None else node
    entry = nodes[node]
    op, args = entry['op'], entry.get('args', [])
    def at(which, time=step):
        return oracle(nodes, alphabet, trace, args[which], time)
    if op == 'atom':
        return trace[step][alphabet.index(entry['proposition'])]
    if op in ('true', 'false'):
        return op == 'true'
    if op == 'not':
        return not at(0)
    if op == 'and':
        return at(0) and at(1)
    if op == 'or':
        return at(0) or at(1)
    if op == 'implies':
        return not at(0) or at(1)
    if op == 'next':
        return step + 1 < len(trace) and at(0, step + 1)
    if op == 'eventually':
        return any(at(0, i) for i in range(step, len(trace)))
    if op == 'always':
        return all(at(0, i) for i in range(step, len(trace)))
    return any(at(1, end) and all(at(0, i) for i in range(step, end))
               for end in range(step, len(trace)))


def check_explanations(inputs, result):
    width = len(inputs['alphabet'])
    flat = sum(inputs['trace'], [])
    def matrix(values):
        return [list(values[i:i + width]) for i in range(0, len(values), width)]
    def verdict(values):
        return oracle(inputs['formula'], inputs['alphabet'], matrix(values))
    actual = verdict(flat)
    assert result['verdict'] is actual
    possibilities = list(product((False, True), repeat=len(flat)))
    def indices(observations):
        out = {item['step'] * width + inputs['alphabet'].index(item['proposition'])
               for item in observations}
        assert len(out) == len(observations)
        assert all(item['value'] is flat[item['step'] * width + inputs['alphabet'].index(item['proposition'])]
                   for item in observations)
        return out
    def sufficient(fixed):
        return all(verdict(values) is actual for values in possibilities
                   if all(values[i] == flat[i] for i in fixed))
    def flipping(free):
        return any(verdict(values) is not actual for values in possibilities
                   if all(values[i] == flat[i] for i in range(len(flat)) if i not in free))
    assert sufficient(indices(result['sufficient_observations']))
    reason = indices(result['subset_minimal_sufficient'])
    assert sufficient(reason)
    assert all(not sufficient(reason - {i}) for i in reason)
    flip = result['outcome_flipping']
    if flip is None:
        assert result['flipping_status'] == 'IMPOSSIBLE'
        assert not flipping(set(range(len(flat))))
    else:
        assert result['flipping_status'] == 'EXISTS'
        free = indices(flip['observations'])
        assert flipping(free)
        assert all(not flipping(free - {i}) for i in free)
        witness = sum(flip['witness'], [])
        assert verdict(witness) is not actual
        assert flip['verdict'] is not actual
        assert all(witness[i] == flat[i] for i in range(len(flat)) if i not in free)


def test_all_sixteen_request_response_traces():
    inputs = request()
    positives = 0
    for values in product((False, True), repeat=4):
        inputs['trace'] = [list(values[:2]), list(values[2:])]
        result = execute(inputs)
        assert result['status'] == 'COMPLETE'
        assert result['completions_checked'] == result['completion_count'] == 16
        check_explanations(inputs, result)
        positives += result['verdict']
    assert positives == 6


def test_strong_next_endpoint_catches_weak_next_mutation():
    inputs = request()
    inputs['trace'] = [[False, False], [True, True]]
    result = execute(inputs)
    assert result['verdict'] is False  # req at last step cannot be answered later
    assert result['verdict'] != (not inputs['trace'][0][0] or inputs['trace'][1][1])
    inputs = {'alphabet': ['p'], 'trace': [[True]], 'source': 'synthetic',
              'formula': [{'op': 'true'}, {'op': 'next', 'args': [0]}]}
    assert execute(inputs)['verdict'] is False
    inputs['formula'].append({'op': 'not', 'args': [1]})
    assert execute(inputs)['verdict'] is True


@pytest.mark.parametrize('op,expected', [('true', True), ('false', False)])
def test_constant_empty_reasons_and_no_flipping_set(op, expected):
    inputs = {'alphabet': ['p'], 'trace': [[False]], 'source': 'constant model', 'formula': [{'op': op}]}
    result = execute(inputs)
    assert result['verdict'] is expected
    assert result['subset_minimal_sufficient'] == []
    check_explanations(inputs, result)


def test_independent_temporal_operator_oracle():
    rng = random.Random(261035169)
    unary = ['not', 'next', 'eventually', 'always']
    binary = ['and', 'or', 'implies', 'until']
    for length in (1, 2, 3):
        for _ in range(24):
            nodes = [{'op': 'atom', 'proposition': 'p'}, {'op': 'atom', 'proposition': 'q'},
                     {'op': 'true'}, {'op': 'false'}]
            for index in range(4, 12):
                op = rng.choice(unary + binary)
                nodes.append({'op': op, 'args': [rng.randrange(index) for _ in range(1 if op in unary else 2)]})
            for bits in product((False, True), repeat=length * 2):
                trace = [list(bits[i:i+2]) for i in range(0, len(bits), 2)]
                inputs = Input(alphabet=['p', 'q'], trace=trace, formula=nodes, source='synthetic')
                assert _evaluate(inputs.formula, inputs.alphabet, inputs.trace) is oracle(nodes, inputs.alphabet, trace)
            # Public operation checked against separate exhaustive completion logic.
            check_explanations(inputs.model_dump(mode='json'), execute(inputs.model_dump(mode='json')))


@pytest.mark.parametrize('budget', [1, 2, 15])
def test_partial_never_claims_absence_or_minimality(budget):
    inputs = request()
    inputs['max_completions'] = budget
    result = execute(inputs)
    assert result['status'] == 'PARTIAL'
    assert result['completions_checked'] == budget
    assert result['completion_count'] == 16
    assert result['subset_minimal_sufficient'] is None
    assert result['outcome_flipping'] is None
    assert result['flipping_status'] == 'UNKNOWN'
    assert len(result['sufficient_observations']) == 4


@pytest.mark.parametrize('updates', [
    {'trace': []}, {'trace': [[True]]}, {'trace': [[True, 1], [False, True]]},
    {'trace': [[True, False]] * 7}, {'alphabet': []}, {'alphabet': ['p', 'p']},
    {'alphabet': ['', 'q']}, {'alphabet': ['x' * 65, 'q']},
    {'formula': []}, {'formula': [{'op': 'true'}] * 65},
    {'formula': [{'op': 'atom', 'proposition': 'absent'}]},
    {'formula': [{'op': 'next', 'args': [0]}]},
    {'formula': [{'op': 'true'}, {'op': 'next', 'args': [-1]}]},
    {'formula': [{'op': 'true'}, {'op': 'next', 'args': [True]}]},
    {'formula': [{'op': 'true'}, {'op': 'and', 'args': [0]}]},
    {'formula': [{'op': 'true', 'proposition': 'request'}]},
    {'formula': [{'op': '__import__'}]}, {'max_completions': 0},
    {'max_completions': 4097}, {'max_completions': True}, {'source': ''}, {'extra': 1},
])
def test_malformed_and_limits_rejected(updates):
    inputs = request()
    inputs.update(updates)
    with pytest.raises(ValueError):
        execute(inputs)


def test_maximum_cells_and_nodes():
    inputs = {'alphabet': ['p'], 'trace': [[False]] * 12, 'source': 'bounded synthetic',
              'formula': [{'op': 'atom', 'proposition': 'p'}] +
                         [{'op': 'not', 'args': [i]} for i in range(63)]}
    result = execute(inputs)
    assert result['completions_checked'] == 4096
    assert result['subset_minimal_sufficient'] == [{'step': 0, 'proposition': 'p', 'value': False}]


def test_detached_discovery_inputs_outputs_and_json():
    inputs = request()
    original = deepcopy(inputs)
    envelope = run('trace.explain', inputs)
    assert inputs == original
    assert json.loads(json.dumps(envelope)) == envelope
    assert catalog.REGISTRY['trace.explain'].result.model_validate(envelope['result'])
    inputs['trace'][0][0] = False
    envelope['result']['sufficient_observations'][0]['value'] = False
    assert execute(original)['sufficient_observations'][0]['value'] is True
    example = catalog.REGISTRY['trace.explain'].contract()['example']
    example['formula'][0]['proposition'] = 'mutant'
    assert request() == original
    assert any(item['operation_id'] == 'trace.explain' for item in find('finite trace explanation'))


def test_cli_and_mcp():
    inputs = request()
    proc = subprocess.run([sys.executable, '-m', 'polya', 'run', 'trace.explain',
                           '--json', json.dumps(inputs), '--result-only'], capture_output=True, text=True, check=True)
    assert json.loads(proc.stdout) == execute(inputs)
    from polya.mcp_server import Server
    server = Server()
    server.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',
                   'params': {'protocolVersion': '2025-06-18'}})
    server.handle({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
    response = server.handle({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call',
                                'params': {'name': 'puzzle.run', 'arguments': {
                                    'operation_id': 'trace.explain', 'inputs': inputs}}})
    assert not response['result']['isError']
    assert response['result']['structuredContent']['data']['result'] == execute(inputs)


def test_recorded_explanation_survives_restart_and_replay(tmp_path):
    from polya.workspace import Workspace
    inputs = request()
    with Workspace(tmp_path) as workspace:
        recorded = workspace.run_recorded('trace.explain', inputs)
        event_id = recorded['ledger_event_id']
    inputs['formula'][2]['op'] = 'eventually'
    with Workspace(tmp_path) as workspace:
        loaded = workspace.load_recorded(event_id)
        assert loaded['inputs']['formula'][2]['op'] == 'next'
        replay = workspace.replay_recorded(event_id)
        assert replay['result'] == recorded['result']


def test_subset_minimal_is_not_minimum_cardinality():
    inputs = {'alphabet': ['p', 'q', 'r'], 'trace': [[True, True, True]], 'source': 'synthetic',
              'formula': [{'op': 'atom', 'proposition': 'p'},
                          {'op': 'atom', 'proposition': 'q'},
                          {'op': 'atom', 'proposition': 'r'},
                          {'op': 'and', 'args': [1, 2]}, {'op': 'or', 'args': [0, 3]}]}
    result = execute(inputs)
    assert [item['proposition'] for item in result['subset_minimal_sufficient']] == ['q', 'r']
    # {p=True} is a smaller sufficient set, so the algorithm is not an optimizer.
    assert all(oracle(inputs['formula'], inputs['alphabet'], [[True, q, r]])
               for q, r in product((False, True), repeat=2))
    check_explanations(inputs, result)
