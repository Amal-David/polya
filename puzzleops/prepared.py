"""Immutable machine snapshots for repeated local replay, with no global model cache."""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from .automata import Machine

SCOPE = 'Exact replay of the supplied deterministic model, not the real puzzle.'


@dataclass(frozen=True, slots=True)
class PreparedMachine:
    kind: str
    states: tuple[str, ...]
    alphabet: tuple[int | str, ...]
    initial: int
    accepting: frozenset[int]
    symbol_ids: Mapping[int | str, int]
    targets: tuple[tuple[int, ...], ...]
    emissions: tuple[tuple[str | None, ...], ...]

    def _symbols(self, word: list | tuple) -> list[int]:
        if type(word) not in (list, tuple) or len(word) > 10000:
            raise ValueError('word must contain at most 10000 symbols')
        if any(type(a) not in (int, str) or a not in self.symbol_ids for a in word):
            raise ValueError('word contains a symbol outside the declared alphabet')
        return [self.symbol_ids[a] for a in word]

    def outputs(self, word: list | tuple) -> list[str]:
        """Mealy output-only replay; useful inside bounded conformance testing."""
        if self.kind != 'mealy':
            raise ValueError('output-only replay requires a Mealy machine')
        state = self.initial
        result = []
        for symbol in self._symbols(word):
            result.append(self.emissions[state][symbol])
            state = self.targets[state][symbol]
        return result

    def simulate(self, word: list[int | str]) -> dict:
        if type(word) is not list:
            raise ValueError('word must be a list of at most 10000 symbols')
        symbols = self._symbols(word)
        state = self.initial
        trace, outputs = [self.states[state]], []
        for symbol in symbols:
            if state >= 0:
                if self.kind == 'mealy':
                    outputs.append(self.emissions[state][symbol])
                state = self.targets[state][symbol]
            trace.append(self.states[state] if state >= 0 else None)
        return {'final_state': self.states[state] if state >= 0 else None,
                'state_trace': trace, 'outputs': outputs,
                'accepted': state in self.accepting if self.kind == 'dfa' else None,
                'scope': SCOPE}


def prepare_machine(machine: Machine | dict) -> PreparedMachine:
    """Validate a detached snapshot; mutating the caller's model cannot change it."""
    raw = machine.model_dump() if isinstance(machine, Machine) else machine
    model = Machine.model_validate(raw)
    ids = {state: i for i, state in enumerate(model.states)}
    symbols = {symbol: i for i, symbol in enumerate(model.alphabet)}
    targets = [[-1] * len(symbols) for _ in ids]
    emissions = [[None] * len(symbols) for _ in ids]
    for edge in model.transitions:
        i, j = ids[edge.source], symbols[edge.symbol]
        targets[i][j] = ids[edge.target]
        emissions[i][j] = edge.output
    return PreparedMachine(model.kind, tuple(model.states), tuple(model.alphabet),
                           ids[model.initial], frozenset(ids[s] for s in model.accepting),
                           MappingProxyType(symbols), tuple(map(tuple, targets)),
                           tuple(map(tuple, emissions)))


def simulate_many(machine: Machine | dict, words: list[list[int | str]]) -> dict:
    if type(words) is not list or len(words) > 256:
        raise ValueError('at most 256 words per batch')
    if any(type(w) is not list for w in words) or sum(map(len, words)) > 10000:
        raise ValueError('batch must contain lists totaling at most 10000 symbols')
    prepared = prepare_machine(machine)
    return {'results': [prepared.simulate(word) for word in words],
            'word_count': len(words), 'symbol_count': sum(map(len, words)),
            'scope': SCOPE}
