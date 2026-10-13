from dataclasses import FrozenInstanceError
from itertools import product
import random
import pytest
from polya import run
from polya.automata import Machine, simulate, from_runs
from polya.prepared import prepare_machine, simulate_many


@pytest.mark.parametrize('seed', range(30))
def test_prepared_matches_independent_original_replay(seed):
    rng = random.Random(seed)
    states = ['a', 'b', 'c']
    raw = {'kind': 'mealy', 'states': states, 'alphabet': [0, '0'], 'initial': 'a',
           'transitions': [{'source': s, 'symbol': a, 'target': rng.choice(states),
                            'output': str(rng.randrange(3))} for s in states for a in [0, '0']]}
    model = Machine.model_validate(raw)
    prepared = prepare_machine(model)
    for size in range(5):
        for word in product([0, '0'], repeat=size):
            assert prepared.simulate(list(word)) == simulate(model, list(word))
            assert prepared.outputs(word) == simulate(model, list(word))['outputs']


def test_partial_dfa_sink_empty_words_and_batch_contract():
    machine = from_runs([2])['machine']
    words = [[], [0], [1,1], [1,0,1], [1,1,0], [1,1,1,0]]
    out = run('automata.simulate_many', {'machine': machine, 'words': words})
    assert out['result']['results'] == [simulate(machine,w) for w in words]
    assert not out['receipt']['independently_reproduced']
    assert simulate_many(machine, [])['results'] == []


def test_snapshot_is_detached_and_immutable():
    model = Machine.model_validate(from_runs([1])['machine'])
    p = prepare_machine(model)
    model.transitions.clear()
    assert p.simulate([1])['accepted']
    with pytest.raises(TypeError): p.symbol_ids[2] = 9
    with pytest.raises(FrozenInstanceError): p.initial = 10
    # Bypassing Pydantic assignment checks must not bypass snapshot validation.
    model.initial = 'missing'
    with pytest.raises(ValueError): prepare_machine(model)


@pytest.mark.parametrize('words', [[[True]], [[2]], [list(range(10001))], [[]]*257, ['abc']])
def test_batch_limits_and_types(words):
    with pytest.raises(ValueError): simulate_many(from_runs([1])['machine'], words)

