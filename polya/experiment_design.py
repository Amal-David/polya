"""Choose informative tests from explicit, conditional hypothesis predictions."""
from __future__ import annotations
from fractions import Fraction
from math import log2
from typing import Literal
from pydantic import Field
from .cryptic import Spec


class Hypothesis(Spec):
    id: str = Field(min_length=1, max_length=64)
    mechanism: str = Field(min_length=1, max_length=256)
    source: str = Field(min_length=1, max_length=512)
    weight: int = Field(default=1, ge=1, le=1000000)


class Test(Spec):
    id: str = Field(min_length=1, max_length=64)
    question: str = Field(min_length=1, max_length=1000)
    cost: int = Field(ge=1, le=1000000)
    predictions: dict[str, str | None] = Field(max_length=64)
    source: str = Field(min_length=1, max_length=512)


class Input(Spec):
    hypotheses: list[Hypothesis] = Field(min_length=2, max_length=64)
    tests: list[Test] = Field(min_length=1, max_length=128)
    criterion: Literal['separation_per_cost', 'separation'] = 'separation_per_cost'


def rank_tests(hypotheses: list[dict], tests: list[dict], criterion: str = 'separation_per_cost') -> dict:
    p = Input(hypotheses=hypotheses, tests=tests, criterion=criterion)
    ids = {h.id for h in p.hypotheses}
    if len(ids) != len(p.hypotheses) or len({t.id for t in p.tests}) != len(p.tests):
        raise ValueError('hypothesis and test IDs must be distinct')
    weights = {h.id: h.weight for h in p.hypotheses}
    total = sum(weights.values())
    pairs = [(a.id, b.id, a.weight * b.weight) for i, a in enumerate(p.hypotheses) for b in p.hypotheses[i+1:]]
    denom = sum(w for _, _, w in pairs)
    rows = []
    for t in p.tests:
        if not set(t.predictions) <= ids or any(v is not None and (not v or len(v) > 256) for v in t.predictions.values()):
            raise ValueError('predictions must name existing hypotheses and bounded nonempty outcome labels or null')
        separated, unresolved = 0, 0
        partitions: dict[str, list[str]] = {}
        for hid in sorted(ids):
            output = t.predictions.get(hid)
            if output is not None:
                partitions.setdefault(output, []).append(hid)
        for a, b, weight in pairs:
            x, y = t.predictions.get(a), t.predictions.get(b)
            if x is None or y is None:
                unresolved += weight
            elif x != y:
                separated += weight
        fraction = Fraction(separated, denom)
        score = fraction / t.cost if criterion == 'separation_per_cost' else fraction
        all_known = all(t.predictions.get(hid) is not None for hid in ids)
        entropy = None
        if all_known:
            masses = [sum(weights[hid] for hid in group) / total for group in partitions.values()]
            entropy = -sum(w * log2(w) for w in masses)
        rows.append({'id': t.id, 'question': t.question, 'cost': t.cost, 'source': t.source,
                     'separation_numerator': fraction.numerator, 'separation_denominator': fraction.denominator,
                     'priority_score': float(score), 'partitions': partitions,
                     'unpredicted': sorted(hid for hid in ids if t.predictions.get(hid) is None),
                     'unresolved_pair_mass': str(Fraction(unresolved, denom)),
                     'information_bits_if_model_correct': entropy, '_score': score})
    rows.sort(key=lambda r: (-r['_score'], r['cost'], r['id']))
    for row in rows:
        del row['_score']
    useful = rows[0]['separation_numerator'] > 0
    return {'tests': rows, 'next_test_id': rows[0]['id'] if useful else None,
            'status': 'RANKED' if useful else 'NO_DISCRIMINATING_TEST',
            'weight_convention': 'Explicit relative caller weights; default equal weight per supplied hypothesis. Not empirical probabilities.',
            'scope': 'Separates only supplied deterministic predictions. Unknown predictions receive no credit. No observation was acquired, hypothesis eliminated, or calibration established. Duplicated/correlated hypotheses can bias weights; consolidate them before ranking.'}


def operations(make):
    return [make('experiment.rank_tests', 'Choose a discriminating next experiment',
                 'Rank explicit predicted disagreements per cost; preserve missing predictions instead of treating them as evidence.',
                 Input, rank_tests, 'next experiment information gain hypothesis discriminate prioritize uncertainty',
                 'Conditional test ranking, not proof or measured chance of solving.', '64 hypotheses,128 tests; finite pairwise accounting.',
                 example={'hypotheses': [{'id': 'a', 'mechanism': 'row reading', 'source': 'clue'}, {'id': 'b', 'mechanism': 'column reading', 'source': 'clue'}],
                          'tests': [{'id': 'first-symbol', 'question': 'What is the first extracted symbol?', 'cost': 1, 'predictions': {'a': 'A', 'b': 'B'}, 'source': 'model predictions'}]},
                 tests=list[dict], next_test_id=str | None, status=str, weight_convention=str, scope=str)]
