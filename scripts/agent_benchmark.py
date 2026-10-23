"""Three-condition synthetic benchmark protocol and independent external-run scorer.

This module never starts a model, purchases execution or treats scripted controls
as LLM evidence. The ordinary-code/direct/composed policies are runner contracts.
"""
from __future__ import annotations

from collections import defaultdict
import hashlib
from itertools import permutations, product
import math
from pathlib import Path
from typing import Any, Literal

from pydantic import Field

from polya import run
from polya.catalog import canonical_json, implementation_fingerprint
from polya.cryptic import Spec
from polya.evaluation import check_answer, generate_cases

CONDITIONS = ('ordinary_coding', 'polya_primitives', 'polya_workflow')
SPLIT_SEEDS = {'development': 421, 'heldout': 79421}
POLICIES = {
    'ordinary_coding': 'Use ordinary coding tools and the supplied rules; do not invoke Polya.',
    'polya_primitives': 'Discover and call Polya primitives directly, with ordinary coding tools available.',
    'polya_workflow': 'Use the documented Polya workflow: inspect inputs, state assumptions, execute bounded operations, verify and preserve request-bound receipts. Count all workflow and council costs.',
}
_SCRIPT_ROOT = Path(__file__).resolve().parent
_HARNESS_SHA256 = hashlib.sha256(b''.join(
    name.encode() + b'\0' + (_SCRIPT_ROOT / name).read_bytes()
    for name in ('agent_benchmark.py', 'evaluate_agents.py'))).hexdigest()


class Budgets(Spec):
    tokens: int = Field(default=8000, ge=1, le=10000000)
    tool_calls: int = Field(default=40, ge=1, le=100000)
    wall_ms: int = Field(default=120000, ge=1, le=86400000)


class Telemetry(Spec):
    # Null is unknown. Full-session wall time includes reading, coding, repairs,
    # council callbacks, execution and verification, not only successful calls.
    wall_ms: int | None = Field(default=None, ge=0, le=864000000)
    tokens: int | None = Field(default=None, ge=0, le=100000000)
    tool_calls: int | None = Field(default=None, ge=0, le=1000000)
    peak_memory_bytes: int | None = Field(default=None, ge=0, le=2**50)
    first_call_valid: bool | None = None
    repair_turns: int | None = Field(default=None, ge=0, le=1000000)
    council_wall_ms: int | None = Field(default=None, ge=0, le=864000000)
    council_tokens: int | None = Field(default=None, ge=0, le=100000000)


class Record(Spec):
    case_id: str = Field(min_length=1, max_length=64)
    condition: Literal['ordinary_coding', 'polya_primitives', 'polya_workflow']
    model_id: str = Field(min_length=1, max_length=256)
    execution_kind: Literal['actual_llm', 'scripted_control']
    protocol_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    input_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    status: Literal['completed', 'timeout', 'failed']
    answer: Any = None
    claimed_solved: bool = False
    budget: Budgets
    metrics: Telemetry = Field(default_factory=Telemetry)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode('utf8')).hexdigest()


def _cases(split: str, per_family: int) -> list[dict]:
    if split not in SPLIT_SEEDS or type(per_family) is not int or not 1 <= per_family <= 30:
        raise ValueError('split must be development/heldout; per_family must be 1..30')
    # Existing generator families have very different semantic diversity. Seeds
    # alone repeat queens/counter/count tasks. Partition actual instance content,
    # then deduplicate; per_family is a cap, not a promise to duplicate fixtures.
    selected, seen, counts = [], set(), defaultdict(int)
    for case in generate_cases(SPLIT_SEEDS[split], 100):
        family, instance = case['family'], case['instance']
        semantic = digest({'family': family, 'instance': instance})
        if family == 'spatial':
            eligible = instance['n'] in ((4, 5) if split == 'development' else (6, 7))
        elif family == 'interactive':
            eligible = instance['period'] in ((2, 3, 4) if split == 'development' else (5, 6, 7))
        else:
            eligible = int(semantic[:2], 16) % 2 == (0 if split == 'development' else 1)
        if not eligible or semantic in seen or counts[family] >= per_family:
            continue
        seen.add(semantic)
        counts[family] += 1
        case['id'] = split + ':' + case['id']
        if case['family'] in ('spatial', 'sequence', 'logic'):
            case['prompt'] += ' Of all valid lists, return the lexicographically smallest.'
        elif case['family'] == 'interactive':
            case['prompt'] += ' Return a shortest sequence; break ties lexicographically with read before tick.'
        selected.append(case)
    if set(counts) != {'text', 'spatial', 'temporal', 'sequence', 'logic', 'interactive'}:
        raise ValueError('generator pool did not cover every declared family')
    return selected


def canonical_answer(case: dict) -> Any:
    """Independent tiny-domain oracle; never calls Polya transformation/solver kernels."""
    family, instance = case['family'], case['instance']
    if family == 'text':
        grid = [instance['text'][i:i + instance['columns']]
                for i in range(0, len(instance['text']), instance['columns'])]
        if instance['order'].startswith('column'):
            lines = [''.join(row[j] for row in grid) for j in range(instance['columns'])]
        else:
            lines = grid
        if instance['order'].endswith('snake'):
            lines = [line[::-1] if i % 2 else line for i, line in enumerate(lines)]
        answer = ''.join(lines)
        return answer[::-1] if instance['reverse'] else answer
    if family == 'temporal':
        first = instance['start']
        return [first, first + instance['gap1'], first + instance['gap1'] + instance['gap2']]
    if family == 'spatial':
        candidates = permutations(range(instance['n']))
    elif family == 'sequence':
        candidates = product((0, 1), repeat=instance['length'])
    elif family == 'logic':
        candidates = product((0, 1), repeat=instance['size'])
    elif family == 'interactive':
        for length in range(1, instance['period'] + 1):
            for actions in product(('read', 'tick'), repeat=length):
                if check_answer(case, list(actions)):
                    return list(actions)
        raise AssertionError('generated counter fixture has no distinguishing input')
    else:
        raise ValueError('unknown benchmark family')
    for candidate in candidates:
        if check_answer(case, list(candidate)):
            return list(candidate)
    raise AssertionError('generated fixture has no valid witness')


def protocol(split: str = 'heldout', per_family: int = 10, budget: dict | None = None) -> dict:
    """Export one identical task set and one budget for every condition; omit answers."""
    budgets = Budgets.model_validate({} if budget is None else budget).model_dump()
    cases = _cases(split, per_family)
    manifest = {
        'schema_version': 1, 'split': split, 'generator': 'polya.evaluation.generate_cases',
        'generator_seed': SPLIT_SEEDS[split], 'per_family': per_family,
        'per_family_counts': {family: sum(case['family'] == family for case in cases)
                              for family in sorted({case['family'] for case in cases})},
        'conditions': list(CONDITIONS), 'policies': POLICIES.copy(), 'budget': budgets,
        'cases': [{**case, 'input_sha256': digest(case)} for case in cases],
        'implementation_fingerprint': implementation_fingerprint(),
        'harness_sha256': _HARNESS_SHA256,
        'oracle_policy': 'Exact canonical answer: lexicographically least witness; shortest then lexical interactive input. Independent supplied-rule checker also runs.',
        'runner_visibility': 'Provide exported task fields and assigned tool/docs only. Keep evaluator/oracle source, expected answers and other-condition traces outside model task contexts; the runner must enforce this separation.',
        'model_run_status': 'not_run',
        'split_policy': 'Semantic deduplication and disjoint content partitions. Queens development n=4,5/heldout n=6,7; counters development period=2,3,4/heldout=5,6,7. Other families partition by parity of the semantic family+instance SHA256. Sample from 100 generated fixtures/family; per_family is an upper cap. Low-diversity families contribute fewer tasks, never repeated instances.',
        'scope': 'Synthetic nonfinancial tasks. Disjoint semantic instances and parameter strata, not secret corpus or family holdout. Freeze protocol before opening heldout cases; do not tune on heldout results. Use per-family macro accuracy because family counts differ.',
    }
    return {**manifest, 'protocol_sha256': digest(manifest),
            'record_schema': Record.model_json_schema()}


def percentiles(values: list[int]) -> dict:
    if not values:
        return {'reported_count': 0, 'p50': None, 'p95': None, 'mean': None}
    ordered = sorted(values)
    def at(fraction: float):
        position = fraction * (len(ordered) - 1)
        low = math.floor(position)
        high = math.ceil(position)
        return ordered[low] + (ordered[high] - ordered[low]) * (position - low)
    return {'reported_count': len(values), 'p50': at(.5), 'p95': at(.95),
            'mean': sum(values) / len(values)}


def score(manifest: dict, records: list[dict], model_id: str) -> dict:
    """Validate paired identities, verify answers, then invoke utility.compare_runs."""
    # Reconstruct rather than trusting a modified manifest's task or budget text.
    expected = protocol(manifest.get('split'), manifest.get('per_family'), manifest.get('budget'))
    if canonical_json(manifest) != canonical_json(expected):
        raise ValueError('manifest differs from the current declared protocol; regenerate explicitly')
    if type(records) is not list or len(records) > len(expected['cases']) * len(CONDITIONS):
        raise ValueError('too many records')
    cases = {case['id']: case for case in _cases(expected['split'], expected['per_family'])}
    input_hashes = {case['id']: case['input_sha256'] for case in expected['cases']}
    answers = {cid: canonical_answer(case) for cid, case in cases.items()}
    tasks = [{'id': cid, 'family': case['family'], 'input_sha256': input_hashes[cid],
              'answer_sha256': digest(answers[cid])} for cid, case in cases.items()]
    episodes, seen, kinds = [], set(), set()
    observed: dict[str, list[Record]] = defaultdict(list)
    for raw in records:
        record = Record.model_validate(raw)
        key = (record.condition, record.case_id)
        if key in seen or record.case_id not in cases:
            raise ValueError('duplicate or unknown condition/task record')
        seen.add(key)
        if (record.protocol_sha256 != expected['protocol_sha256'] or
                record.input_sha256 != input_hashes[record.case_id] or record.model_id != model_id or
                record.budget.model_dump() != expected['budget']):
            raise ValueError('paired model, protocol, input and equal budget identities must match')
        if len(canonical_json(record.answer).encode('utf8')) > 65536:
            raise ValueError('answer exceeds 64 KB')
        kinds.add(record.execution_kind)
        if len(kinds) > 1:
            raise ValueError('scripted controls and actual LLM records must be scored separately')
        metrics = record.metrics
        if metrics.tool_calls == 0 and (metrics.first_call_valid is not None or
                                       metrics.repair_turns not in (None, 0)):
            raise ValueError('zero tool calls require unknown first-call validity and no repair turns')
        if ((metrics.council_wall_ms is not None and metrics.wall_ms is not None and
             metrics.council_wall_ms > metrics.wall_ms) or
                (metrics.council_tokens is not None and metrics.tokens is not None and
                 metrics.council_tokens > metrics.tokens)):
            raise ValueError('council costs must be included within full-session totals')
        # Invalid/noncanonical answers are retained as failures, never repaired.
        valid = check_answer(cases[record.case_id], record.answer)
        canonical = canonical_json(record.answer) == canonical_json(answers[record.case_id])
        exact = valid and canonical and record.status == 'completed'
        answer_bytes = canonical_json(record.answer).encode('utf8') if exact else None
        episodes.append({'task_id': record.case_id, 'condition': record.condition,
            'model_id': record.model_id, 'input_sha256': record.input_sha256,
            'answer_hex': answer_bytes.hex() if answer_bytes is not None else None,
            'claimed_solved': record.claimed_solved, 'wall_ms': metrics.wall_ms,
            'tokens': metrics.tokens, 'tool_calls': metrics.tool_calls})
        observed[record.condition].append(record)
    utility = run('utility.compare_runs', {'tasks': tasks, 'conditions': list(CONDITIONS),
        'model_id': model_id, 'budget': expected['budget'], 'episodes': episodes})
    summaries = {}
    names = ('wall_ms', 'tokens', 'tool_calls', 'peak_memory_bytes', 'repair_turns',
             'council_wall_ms', 'council_tokens')
    for condition in CONDITIONS:
        rows = observed[condition]
        first_calls = [row.metrics.first_call_valid for row in rows
                       if row.metrics.first_call_valid is not None]
        summaries[condition] = {
            'first_valid_call_rate': sum(first_calls) / len(first_calls) if first_calls else None,
            'first_call_reported_count': len(first_calls),
            'status_counts': {status: sum(row.status == status for row in rows)
                              for status in ('completed', 'timeout', 'failed')},
            'telemetry': {name: percentiles([getattr(row.metrics, name) for row in rows
                                           if getattr(row.metrics, name) is not None]) for name in names},
        }
    kind = next(iter(kinds)) if kinds else None
    return {
        'protocol_sha256': expected['protocol_sha256'], 'split': expected['split'],
        'model_id': model_id, 'execution_kind': kind,
        'model_run_status': 'not_run' if kind != 'actual_llm' else
            'runner_reported_complete' if len(records) == len(cases) * 3 else 'runner_reported_partial',
        'conditions': utility['result']['conditions'],
        'telemetry': summaries,
        'paired_success_only_latency': utility['result']['paired'],
        'scorer_receipt': utility['receipt'],
        'agent_speedup_established': False,
        'scope': 'Independent supplied-rule and canonical-answer checks; missing runs count as failures. Null telemetry remains unknown and prevents budget qualification. All-task accuracy and false claims precede success-only latency. External runner telemetry and model identity are declared, not authenticated. Scripted controls do not measure LLM utility. Council costs must already be included in session totals.',
    }


def self_check(manifest: dict) -> dict:
    """Exercise scoring with oracle outputs, without pretending to run three agents."""
    rows = []
    cases = _cases(manifest['split'], manifest['per_family'])
    for case in cases:
        answer = canonical_answer(case)
        assert check_answer(case, answer)
        for condition in CONDITIONS:
            rows.append({'case_id': case['id'], 'condition': condition,
                'model_id': 'scripted-oracle-self-check', 'execution_kind': 'scripted_control',
                'protocol_sha256': manifest['protocol_sha256'], 'input_sha256': digest(case),
                'status': 'completed', 'answer': answer, 'claimed_solved': True,
                'budget': manifest['budget'], 'metrics': {}})
    return {**score(manifest, rows, 'scripted-oracle-self-check'),
            'scope': 'Scorer/oracle self-check only. These are repeated known-answer records, not ordinary-code, direct-tool or composed agent executions. Model performance and all session telemetry remain unrun/unknown.'}
