"""Independent replay and concurrent immutable-snapshot regressions."""
from concurrent.futures import ThreadPoolExecutor
from itertools import product
import random
import pytest
from polya.automata import Machine, from_runs, simulate
from polya.prepared import prepare_machine


@pytest.mark.parametrize('runs', [[], [1], [2], [1, 1], [2, 1]])
def test_prepared_dfa_matches_independent_reference(runs):
    machine = from_runs(runs)['machine']
    prepared = prepare_machine(machine)
    for length in range(7):
        for word in product([0, 1], repeat=length):
            assert prepared.simulate(list(word)) == simulate(machine, list(word))


@pytest.mark.parametrize('seed', range(20))
def test_prepared_mealy_matches_reference(seed):
    rng = random.Random(seed)
    states = [f'q{i}' for i in range(7)]
    machine = {'kind': 'mealy', 'states': states, 'alphabet': [0, 1], 'initial': 'q0',
               'transitions': [{'source': s, 'symbol': a, 'target': rng.choice(states),
                                'output': str(rng.randrange(5))} for s in states for a in [0, 1]]}
    prepared = prepare_machine(machine)
    words = [[rng.randrange(2) for _ in range(rng.randrange(32))] for _ in range(40)]
    expected = [simulate(machine, word) for word in words]
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert list(pool.map(prepared.simulate, words)) == expected


def test_snapshot_is_detached_from_mutable_pydantic_input():
    machine = Machine.model_validate(from_runs([1])['machine'])
    prepared = prepare_machine(machine)
    before = prepared.simulate([0, 1])
    machine.transitions.clear()
    machine.accepting.clear()
    machine.alphabet.clear()
    assert prepared.simulate([0, 1]) == before
    with pytest.raises(TypeError):
        prepared.symbol_ids[0] = 99


@pytest.mark.parametrize('word', [(), [True], ['unknown'], [0] * 10001])
def test_prepared_replay_retains_admission_limits(word):
    with pytest.raises(ValueError):
        prepare_machine(from_runs([1])['machine']).simulate(word)


def test_preparation_revalidates_a_mutated_model():
    machine = Machine.model_validate(from_runs([1])['machine'])
    machine.initial = 'undeclared'
    with pytest.raises(ValueError):
        prepare_machine(machine)
