"""Deterministic sequence models, independent replay, and distinguishing experiments.

No network, shell, or dynamic imports are selected by a machine document.
Partial DFAs have a rejecting sink; Mealy machines must be total.
"""
from __future__ import annotations

from collections import deque
from typing import Literal
import time
from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(strict=True, extra='forbid')


class Transition(StrictModel):
    source: str = Field(min_length=1, max_length=100)
    symbol: int | str
    target: str = Field(min_length=1, max_length=100)
    output: str | None = Field(default=None, max_length=1000)


class Machine(StrictModel):
    kind: Literal['dfa', 'mealy']
    states: list[str] = Field(min_length=1, max_length=1024)
    alphabet: list[int | str] = Field(min_length=1, max_length=64)
    initial: str
    accepting: list[str] = Field(default_factory=list, max_length=1024)
    transitions: list[Transition] = Field(default_factory=list, max_length=65536)

    @model_validator(mode='after')
    def validate_machine(self):
        if len(set(self.states)) != len(self.states) or any(not s or len(s)>100 for s in self.states):
            raise ValueError('states must be distinct, nonempty names of at most 100 characters')
        if len(set(self.alphabet)) != len(self.alphabet):
            raise ValueError('alphabet symbols must be distinct')
        if any(type(a) not in (int, str) or (isinstance(a, str) and len(a)>100) for a in self.alphabet):
            raise ValueError('alphabet symbols must be bounded strings or strict integers')
        if self.initial not in self.states or not set(self.accepting) <= set(self.states):
            raise ValueError('initial and accepting states must be declared')
        if len(set(self.accepting)) != len(self.accepting):
            raise ValueError('accepting states must be distinct')
        seen = set()
        for t in self.transitions:
            if t.source not in self.states or t.target not in self.states or t.symbol not in self.alphabet:
                raise ValueError('transition refers to undeclared state or symbol')
            if (t.source, t.symbol) in seen:
                raise ValueError('transition relation must be deterministic')
            seen.add((t.source, t.symbol))
            if self.kind == 'dfa' and t.output is not None:
                raise ValueError('DFA transitions do not carry outputs')
            if self.kind == 'mealy' and t.output is None:
                raise ValueError('Mealy transitions require output strings')
        if self.kind == 'mealy':
            if self.accepting:
                raise ValueError('Mealy machines use transition outputs, not accepting states')
            if len(seen) != len(self.states)*len(self.alphabet):
                raise ValueError('Mealy machines must be total on the declared alphabet')
        return self


def as_machine(machine: Machine | dict) -> Machine:
    return machine if isinstance(machine, Machine) else Machine.model_validate(machine)


def simulate(machine: Machine | dict, word: list[int | str]) -> dict:
    machine = as_machine(machine)
    if type(word) is not list or len(word)>10000:
        raise ValueError('word must be a list of at most 10000 symbols')
    if any(type(a) not in (int,str) or a not in machine.alphabet for a in word):
        raise ValueError('word contains a symbol outside the declared alphabet')
    table = {(t.source,t.symbol): t for t in machine.transitions}
    state, trace, outputs = machine.initial, [machine.initial], []
    for a in word:
        t = table.get((state, a))
        if t is None:
            state = None  # Explicit rejecting sink, never a learned "unknown" transition.
        else:
            state = t.target
            if machine.kind == 'mealy':
                outputs.append(t.output)
        trace.append(state)
    return {'final_state': state, 'state_trace': trace, 'outputs': outputs,
            'accepted': state in machine.accepting if machine.kind == 'dfa' else None,
            'scope': 'Exact replay of the supplied deterministic model, not the real puzzle.'}


def distinguish(left: Machine | dict, right: Machine | dict, max_pairs: int=100000,
                max_depth: int | None=None, timeout_ms: int=5000) -> dict:
    """BFS of the reachable product; witnesses are shortest in input-symbol length."""
    left, right = as_machine(left), as_machine(right)
    if left.kind != right.kind or set(left.alphabet) != set(right.alphabet):
        raise ValueError('models must have the same kind and alphabet')
    if type(max_pairs) is not int or not 1<=max_pairs<=1_000_000:
        raise ValueError('max_pairs must be in [1,1000000]')
    if max_depth is not None and (type(max_depth) is not int or not 0<=max_depth<=10000):
        raise ValueError('max_depth must be null or in [0,10000]')
    if type(timeout_ms) is not int or not 1<=timeout_ms<=60000:
        raise ValueError('timeout_ms must be in [1,60000]')
    deadline = time.monotonic()+timeout_ms/1000
    lt = {(t.source,t.symbol):t for t in left.transitions}
    rt = {(t.source,t.symbol):t for t in right.transitions}
    start = (left.initial,right.initial)
    parents = {start: None}
    queue = deque([(start,0)])
    expanded, cutoff = 0, False

    def word_to(pair):
        result = []
        while parents[pair] is not None:
            prev, symbol = parents[pair]
            result.append(symbol)
            pair = prev
        return result[::-1]

    def result(status, word=None, reason=None):
        lout = simulate(left,word) if word is not None else None
        rout = simulate(right,word) if word is not None else None
        if status == 'DISTINGUISHED':
            key = 'accepted' if left.kind == 'dfa' else 'outputs'
            if lout[key] == rout[key]:
                raise RuntimeError('Internal error: witness failed independent replay')
        return {'status':status, 'word':word, 'left_replay':lout, 'right_replay':rout,
                'expanded_pairs':expanded, 'discovered_pairs':len(parents),
                'shortest':True if status=='DISTINGUISHED' else None,
                'complete':status in ('EQUIVALENT','DISTINGUISHED'), 'reason':reason,
                'scope':'Equivalence or disagreement of supplied models only; no real observation was acquired.'}

    while queue:
        if time.monotonic()>=deadline:
            return result('UNKNOWN',reason='time_budget')
        pair, depth = queue.popleft()
        expanded += 1
        ls,rs = pair
        if left.kind=='dfa' and ((ls in left.accepting)!=(rs in right.accepting)):
            return result('DISTINGUISHED',word_to(pair))
        if max_depth is not None and depth>=max_depth:
            cutoff=True
            continue
        for a in left.alphabet:
            l,r=lt.get((ls,a)),rt.get((rs,a))
            if left.kind=='mealy' and l.output != r.output:
                return result('DISTINGUISHED',word_to(pair)+[a])
            nxt=(l.target if l else None,r.target if r else None)
            if nxt not in parents:
                if len(parents)>=max_pairs:
                    return result('UNKNOWN',reason='product_pair_budget')
                parents[nxt]=(pair,a)
                queue.append((nxt,depth+1))
    return result('UNKNOWN' if cutoff else 'EQUIVALENT', reason='depth_budget' if cutoff else None)


def from_runs(runs: list[int]) -> dict:
    """Build a partial DFA for binary rows having exactly these positive run lengths."""
    if type(runs) is not list or len(runs)>64 or any(type(r) is not int or not 1<=r<=128 for r in runs):
        raise ValueError('runs must be at most 64 positive integers, each at most 128')
    if sum(runs)+len(runs)>1000:
        raise ValueError('run automaton would exceed the state budget')
    states, edges = ['q0'], []
    state = 0
    for length in runs:
        edges.append({'source':f'q{state}','symbol':0,'target':f'q{state}'})
        for _ in range(length):
            edges.append({'source':f'q{state}','symbol':1,'target':f'q{state+1}'})
            state+=1; states.append(f'q{state}')
        # At least one separator before another run; trailing zero is optional.
        edges.append({'source':f'q{state}','symbol':0,'target':f'q{state+1}'})
        state+=1; states.append(f'q{state}')
    edges.append({'source':f'q{state}','symbol':0,'target':f'q{state}'})
    accepting=[f'q{state}'] if not runs else [f'q{state-1}',f'q{state}']
    machine=Machine(kind='dfa',states=states,alphabet=[0,1],initial='q0',
                    accepting=accepting,transitions=[Transition(**e) for e in edges])
    return {'machine':machine.model_dump(), 'scope':'Binary run-length rule supplied by the caller; not image recognition.'}
