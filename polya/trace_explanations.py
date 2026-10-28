"""Bounded exact explanations for one nonempty, fully observed finite trace.

The flat, backward-referencing formula is data, never executable code. Exhaustive
completion checking establishes one subset-minimal reason, not a smallest reason.
"""
from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from .cryptic import Spec


class Node(Spec):
    op: Literal['atom', 'true', 'false', 'not', 'and', 'or', 'implies',
                'next', 'eventually', 'always', 'until']
    args: list[int] = Field(default_factory=list, max_length=2)
    proposition: str | None = Field(default=None, min_length=1, max_length=64)


class Input(Spec):
    alphabet: list[str] = Field(min_length=1, max_length=12)
    trace: list[list[bool]] = Field(min_length=1, max_length=12)
    formula: list[Node] = Field(min_length=1, max_length=64)
    source: str = Field(min_length=1, max_length=512)
    max_completions: int = Field(default=4096, ge=1, le=4096)

    @model_validator(mode='after')
    def valid_model(self):
        if (len(set(self.alphabet)) != len(self.alphabet) or
                any(not name or len(name) > 64 for name in self.alphabet)):
            raise ValueError('alphabet names must be unique and contain 1-64 characters')
        if any(len(row) != len(self.alphabet) for row in self.trace):
            raise ValueError('each trace row must contain one Boolean per alphabet name')
        if len(self.trace) * len(self.alphabet) > 12:
            raise ValueError('at most 12 Boolean observation cells are supported')
        for index, node in enumerate(self.formula):
            arity = (0 if node.op in ('atom', 'true', 'false') else
                     2 if node.op in ('and', 'or', 'implies', 'until') else 1)
            if len(node.args) != arity or any(ref < 0 or ref >= index for ref in node.args):
                raise ValueError('formula arguments must have the operator arity and refer to earlier nodes')
            if node.op == 'atom':
                if node.proposition not in self.alphabet:
                    raise ValueError('atom must name a declared proposition')
            elif node.proposition is not None:
                raise ValueError('only an atom may carry a proposition')
        return self


class Observation(Spec):
    step: int
    proposition: str
    value: bool


class Flip(Spec):
    observations: list[Observation]
    witness: list[list[bool]]
    verdict: bool
    subset_minimal: Literal[True]


SCOPE = ('Exact explanations relative to the supplied formula, fixed nonempty trace length, '
         'alphabet and independent Boolean completion domain. Source and observation meanings '
         'are caller claims, not authenticated evidence or intended-model fidelity. One '
         'subset-minimal explanation of each kind when it exists, on COMPLETE only; not all '
         'explanations or minimum cardinality. '
         'No causal or real-world intervention claim. Existing symbolic cores are unchanged.')


def _evaluate(formula: list[Node], alphabet: list[str], trace: list[list[bool]]) -> bool:
    """Bottom-up finite semantics; next is strong and false at the endpoint."""
    size = len(trace)
    values: list[list[bool]] = []
    for node in formula:
        op = node.op
        if op == 'atom':
            column = alphabet.index(node.proposition)
            row = [step[column] for step in trace]
        elif op in ('true', 'false'):
            row = [op == 'true'] * size
        else:
            left = values[node.args[0]]
            right = values[node.args[1]] if len(node.args) == 2 else None
            if op == 'not':
                row = [not x for x in left]
            elif op == 'and':
                row = [x and y for x, y in zip(left, right)]
            elif op == 'or':
                row = [x or y for x, y in zip(left, right)]
            elif op == 'implies':
                row = [not x or y for x, y in zip(left, right)]
            elif op == 'next':
                row = left[1:] + [False]
            else:
                row = [False] * size
                tail = op == 'always'
                for step in range(size - 1, -1, -1):
                    if op == 'eventually':
                        tail = left[step] or tail
                    elif op == 'always':
                        tail = left[step] and tail
                    else:  # strong until: the right operand must eventually hold
                        tail = right[step] or (left[step] and tail)
                    row[step] = tail
        values.append(row)
    return values[-1][0]


def explain(**kwargs) -> dict:
    request = Input.model_validate(kwargs)
    width, length = len(request.alphabet), len(request.trace)
    cells = width * length
    full = (1 << cells) - 1
    original = sum(int(value) << i for i, value in enumerate(
        value for row in request.trace for value in row))

    def decode(bits: int) -> list[list[bool]]:
        return [[bool(bits & (1 << (step * width + column))) for column in range(width)]
                for step in range(length)]

    def observations(mask: int) -> list[dict]:
        return [Observation(step=i // width, proposition=request.alphabet[i % width],
                            value=bool(original & (1 << i))).model_dump()
                for i in range(cells) if mask & (1 << i)]

    verdict = _evaluate(request.formula, request.alphabet, request.trace)
    total = 1 << cells
    checked = min(total, request.max_completions)
    # Difference masks include both true and false observed cells. The full
    # completion domain is necessary to certify absence and subset-minimality.
    opposite = [candidate ^ original for candidate in range(checked)
                if _evaluate(request.formula, request.alphabet, decode(candidate)) != verdict]
    complete = checked == total
    result = {'status': 'COMPLETE' if complete else 'PARTIAL', 'verdict': verdict,
              'sufficient_observations': observations(full),
              'subset_minimal_sufficient': None, 'outcome_flipping': None,
              'flipping_status': 'UNKNOWN', 'completions_checked': checked,
              'completion_count': total, 'source': request.source, 'scope': SCOPE}
    if not complete:
        return result
    sufficient = full
    for cell in range(cells):
        candidate = sufficient & ~(1 << cell)
        if all(candidate & difference for difference in opposite):
            sufficient = candidate
    result['subset_minimal_sufficient'] = observations(sufficient)
    result['flipping_status'] = 'EXISTS' if opposite else 'IMPOSSIBLE'
    if opposite:
        free = full
        for cell in range(cells):
            candidate = free & ~(1 << cell)
            if any(difference & ~candidate == 0 for difference in opposite):
                free = candidate
        # Minimality forces every free cell to change in any admissible witness.
        witness_mask = next(difference for difference in opposite if difference & ~free == 0)
        result['outcome_flipping'] = {'observations': observations(free),
                                     'witness': decode(original ^ witness_mask),
                                     'verdict': not verdict, 'subset_minimal': True}
    return result


def operations(make):
    return [make('trace.explain', 'Explain a fixed finite trace verdict',
                 'Check all Boolean completions to distinguish sufficient observations, one subset-minimal reason and one subset-minimal outcome-flipping set.',
                 Input, explain, 'finite trace temporal logic LTLf sufficient subset minimal explanation counterfactual strong next',
                 SCOPE,
                 'Nonempty trace; at most 12 Boolean cells, 64 backward-referencing formula nodes, 4096 completions; caller cap yields PARTIAL without minimality or absence claims. Strong next is false at the endpoint.',
                 example={'alphabet': ['request', 'done'], 'trace': [[True, False], [False, True]],
                          'formula': [{'op': 'atom', 'proposition': 'request'},
                                      {'op': 'atom', 'proposition': 'done'},
                                      {'op': 'next', 'args': [1]},
                                      {'op': 'implies', 'args': [0, 2]},
                                      {'op': 'always', 'args': [3]}],
                          'source': 'Synthetic request/response trace'},
                 status=Literal['COMPLETE', 'PARTIAL'], verdict=bool,
                 sufficient_observations=list[Observation],
                 subset_minimal_sufficient=list[Observation] | None,
                 outcome_flipping=Flip | None,
                 flipping_status=Literal['EXISTS', 'IMPOSSIBLE', 'UNKNOWN'],
                 completions_checked=int, completion_count=int, source=str, scope=str)]
