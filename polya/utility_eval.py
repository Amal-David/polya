"""Paired agent-utility scoring from independently checked answer commitments.

No model calls or automatic positive results. Missing runs count against accuracy;
missing telemetry prevents budget-qualified comparisons rather than implying zero.
"""
from __future__ import annotations
from collections import defaultdict
import hashlib
from statistics import median
from pydantic import Field
from .cryptic import Spec


class Task(Spec):
    id: str = Field(min_length=1, max_length=64)
    family: str = Field(min_length=1, max_length=64)
    input_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    answer_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')


class Budget(Spec):
    tokens: int = Field(ge=1, le=10000000)
    tool_calls: int = Field(ge=1, le=100000)
    wall_ms: int = Field(ge=1, le=86400000)


class Episode(Spec):
    task_id: str = Field(min_length=1, max_length=64)
    condition: str = Field(min_length=1, max_length=64)
    model_id: str = Field(min_length=1, max_length=256)
    input_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    answer_hex: str | None = Field(default=None, max_length=32768)
    claimed_solved: bool = False
    tokens: int | None = Field(default=None, ge=0, le=100000000)
    tool_calls: int | None = Field(default=None, ge=0, le=1000000)
    wall_ms: int | None = Field(default=None, ge=0, le=864000000)


class Input(Spec):
    tasks: list[Task] = Field(min_length=1, max_length=200)
    conditions: list[str] = Field(min_length=2, max_length=3)
    model_id: str = Field(min_length=1, max_length=256)
    budget: Budget
    episodes: list[Episode] = Field(max_length=600)


def compare(**kwargs) -> dict:
    p = Input.model_validate(kwargs)
    tasks = {t.id: t for t in p.tasks}
    if len(tasks) != len(p.tasks) or len(set(p.conditions)) != len(p.conditions):
        raise ValueError('task IDs and condition names must be unique')
    if any(not c or len(c) > 64 for c in p.conditions):
        raise ValueError('condition names must contain 1..64 characters')
    observed = {}
    for e in p.episodes:
        key = (e.condition, e.task_id)
        if e.task_id not in tasks or e.condition not in p.conditions or key in observed:
            raise ValueError('unknown or duplicate condition/task episode')
        if e.model_id != p.model_id or e.input_sha256 != tasks[e.task_id].input_sha256:
            raise ValueError('paired runs must use the declared model and identical task inputs')
        raw = None
        if e.answer_hex is not None:
            if len(e.answer_hex) % 2 or any(c not in '0123456789abcdefABCDEF' for c in e.answer_hex):
                raise ValueError('answer_hex must be exact even-length hex without implicit repair')
            raw = bytes.fromhex(e.answer_hex)
        correct = raw is not None and hashlib.sha256(raw).hexdigest() == tasks[e.task_id].answer_sha256
        measured = all(getattr(e, field) is not None for field in ('tokens', 'tool_calls', 'wall_ms'))
        within = measured and all(getattr(e, field) <= getattr(p.budget, field) for field in ('tokens', 'tool_calls', 'wall_ms'))
        observed[key] = {'correct': correct, 'within_budget': within, 'complete_metrics': measured,
                         'false_claim': e.claimed_solved and not correct, 'episode': e}
    families = defaultdict(list)
    for t in p.tasks:
        families[t.family].append(t.id)
    results = {}
    for condition in p.conditions:
        per_family = {}
        for family, ids in families.items():
            checked = sum(observed.get((condition, tid), {}).get('correct', False) for tid in ids)
            qualified = sum(observed.get((condition, tid), {}).get('correct', False) and
                            observed.get((condition, tid), {}).get('within_budget', False) for tid in ids)
            per_family[family] = {'tasks': len(ids), 'correct': checked, 'budget_qualified_correct': qualified,
                                  'accuracy': checked / len(ids), 'budget_qualified_accuracy': qualified / len(ids)}
        records = [r for (c, _), r in observed.items() if c == condition]
        results[condition] = {'families': per_family, 'missing_runs': len(tasks) - len(records),
                              'missing_metrics': sum(not r['complete_metrics'] for r in records),
                              'false_solution_claims': sum(r['false_claim'] for r in records),
                              'macro_accuracy': sum(r['accuracy'] for r in per_family.values()) / len(per_family),
                              'budget_qualified_macro_accuracy': sum(r['budget_qualified_accuracy'] for r in per_family.values()) / len(per_family)}
    baseline = p.conditions[0]
    paired = {}
    for condition in p.conditions[1:]:
        comparable, ratios = 0, []
        for tid in tasks:
            a, b = observed.get((baseline, tid)), observed.get((condition, tid))
            if a and b and a['complete_metrics'] and b['complete_metrics']:
                comparable += 1
                if a['correct'] and b['correct'] and a['within_budget'] and b['within_budget'] and b['episode'].wall_ms > 0:
                    ratios.append(a['episode'].wall_ms / b['episode'].wall_ms)
        paired[condition] = {'baseline': baseline, 'paired_runs_with_metrics': comparable,
                             'both_correct_within_budget': len(ratios),
                             'median_wall_ratio_on_successful_pairs': median(ratios) if ratios else None,
                             'selection_warning': 'Latency ratio is conditional on both succeeding; inspect all-task accuracy and failures first.'}
    return {'conditions': results, 'paired': paired, 'metrics_are_runner_reported': True,
            'scope': 'Answer bytes are checked against caller commitments; targets and telemetry are not authenticated. Same model/input/budget enforced on declared fields. Missing runs count as incorrect; no LLM was run by this evaluator and no causal/general utility claim follows from synthetic episodes.'}


def operations(make):
    return [make('utility.compare_runs', 'Compare matched agent investigation runs',
                 'Recompute answer correctness; account for missing runs, missing costs and false claims before comparing paired latency.',
                 Input, compare, 'agent eval benchmark utility progress false discoveries matched budget',
                 'Scoring supplied episodes only, not executing models or validating target provenance.',
                 '200 tasks,3 conditions,600 episodes; exact-byte answer bounds.',
                 conditions=dict, paired=dict, metrics_are_runner_reported=bool, scope=str)]
