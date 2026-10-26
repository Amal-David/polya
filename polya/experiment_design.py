"""Choose informative tests from explicit, conditional hypothesis predictions."""
from __future__ import annotations
from fractions import Fraction
import hashlib
from math import log2
from typing import Literal
from pydantic import Field
from .cryptic import Spec
from .extensions import CompareInput
from .model import verify


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


class Observable(Spec):
    """The caller explains how a model variable could actually be observed."""

    variable: str = Field(min_length=1, max_length=100)
    id: str = Field(min_length=1, max_length=64)
    question: str = Field(min_length=1, max_length=1000)
    source: str = Field(min_length=1, max_length=512)
    cost: int = Field(ge=1, le=1000000)


class ComparisonEnvelope(Spec):
    operation_id: Literal['hypotheses.compare']
    result: dict
    receipt: dict
    # Known host metadata is accepted for composition, never as proof of a local
    # execution. Arbitrary extra envelope fields remain invalid.
    ledger_event_id: str | None = Field(default=None, min_length=1, max_length=128)
    request_ref: str | None = Field(default=None, pattern=r'^sha256:[a-f0-9]{64}$')
    response_ref: str | None = Field(default=None, pattern=r'^sha256:[a-f0-9]{64}$')


class FromComparisonInput(Spec):
    comparison_inputs: CompareInput
    comparison: ComparisonEnvelope
    observables: list[Observable] = Field(min_length=1, max_length=128)
    criterion: Literal['separation_per_cost', 'separation'] = 'separation_per_cost'


class ComparisonIdentity(Spec):
    operation_id: Literal['hypotheses.compare']
    operation_version: Literal['3']
    experiment_key: str
    implementation_fingerprint: str
    preparation_implementation_fingerprint: str
    inputs_sha256: str
    result_sha256: str
    model_sha256: str
    cases_sha256: str
    case_ids: list[str]


class CaseEvidence(Spec):
    status: Literal['SAT', 'UNSAT', 'UNKNOWN', 'UNAVAILABLE', 'UNSUPPORTED']
    execution_status: Literal['COMPLETE', 'PARTIAL', 'EXECUTION_ERROR']
    complete: bool
    requested_hypotheses: list[str]
    predicted_variables: list[str]


def _comparison_cases(request: CompareInput, result: dict) -> dict:
    """Validate nested case consistency without repeating the bounded search."""
    from . import catalog

    cases = result['cases']
    # Receipt identity is canonical JSON, and Ledger.run executes a canonical
    # snapshot. Object insertion order is not authenticated execution history.
    if type(cases) is not dict or set(cases) != set(request.cases):
        raise ValueError('comparison case IDs must match the request')
    if any(not name or len(name) > 64 for name in cases):
        raise ValueError('comparison case IDs must contain 1-64 characters for test ranking')
    projection = request.model.projection
    checks = assignments = 0
    failures = {}
    for name, raw in cases.items():
        active = request.model.active(request.cases[name])
        if type(raw) is not dict:
            raise ValueError('each comparison case must be an object')
        if raw.get('reason') == 'shared_budget':
            expected = {'status': 'UNKNOWN', 'complete': False, 'forced_values': {},
                        'reason': 'shared_budget', 'execution_status': 'PARTIAL',
                        'failed_checks': []}
            if catalog.canonical_json(raw) != catalog.canonical_json(expected):
                raise ValueError('an unexecuted shared-budget case cannot carry predictions')
            continue
        # hypotheses.compare reuses analyze but historically exposes cases=dict.
        # Check each full case against that operation's strict result contract.
        case = catalog.REGISTRY['symbolic.analyze'].result.model_validate(raw).model_dump(mode='json')
        if (case['active_constraint_ids'] != [rule.id for rule in active] or
                case['enabled_hypotheses'] != [rule.id for rule in active if rule.kind == 'hypothesis'] or
                len(case['answer_variables']) != len(set(case['answer_variables'])) or
                set(case['answer_variables']) != set(projection) or
                (request.model.answer_variables is not None and case['answer_variables'] != projection)):
            raise ValueError('comparison case constraints, hypotheses or projection do not match its request')
        expected_backends = ('z3', 'reference') if request.backend == 'auto' else (request.backend,)
        if case['backend'] not in expected_backends:
            raise ValueError('comparison case backend does not match its request')
        stats = case['stats']
        if (set(stats) != {'solver_checks', 'reference_assignments_checked', 'elapsed_ms'} or
                type(stats['solver_checks']) is not int or stats['solver_checks'] < 0 or
                type(stats['reference_assignments_checked']) is not int or stats['reference_assignments_checked'] < 0 or
                type(stats['elapsed_ms']) not in (int, float) or stats['elapsed_ms'] < 0):
            raise ValueError('comparison case statistics must be nonnegative bounded work counts')
        checks += stats['solver_checks']
        assignments += stats['reference_assignments_checked']
        if checks > request.max_checks or assignments > request.max_assignments:
            raise ValueError('comparison case statistics exceed the shared request budget')
        forced = case['forced_values']
        if not set(forced) <= set(projection):
            raise ValueError('comparison forced values must name projected variables')
        for variable, value in forced.items():
            if not request.model.variables[variable].contains(value):
                raise ValueError('comparison forced value has the wrong sort or domain')
        failed_checks = case['failed_checks']
        expected_execution = ('EXECUTION_ERROR' if failed_checks else
                              'COMPLETE' if case['complete'] else 'PARTIAL')
        if case['execution_status'] != expected_execution:
            raise ValueError('comparison case execution status is inconsistent')
        if case['status'] in ('UNAVAILABLE', 'UNSUPPORTED'):
            failures[name] = case['status']
            if not failed_checks:
                raise ValueError('a failed comparison case must preserve its failed checks')
        elif failed_checks:
            failures[name] = failed_checks[0]['status']
        if case['status'] != 'SAT':
            if forced or case['assignment'] is not None or case['alternative_assignment'] is not None:
                raise ValueError('only SAT comparison cases may carry witnesses or forced values')
            unsat = case['status'] == 'UNSAT'
            if (case['complete'] != unsat or case['uniqueness'] != ('UNSAT' if unsat else 'UNKNOWN') or
                    case['not_forced'] or set(case['undetermined']) != (set() if unsat else set(projection))):
                raise ValueError('non-SAT comparison case completeness or uniqueness is inconsistent')
            continue
        if (case['uniqueness'] not in ('UNIQUE', 'MULTIPLE', 'UNKNOWN') or
                case['complete'] != (not case['undetermined'] and case['uniqueness'] != 'UNKNOWN')):
            raise ValueError('SAT comparison case completeness or uniqueness is inconsistent')
        assignment = case['assignment']
        if not verify(request.model, assignment, request.cases[name])['valid']:
            raise ValueError('comparison witness failed independent model verification')
        if any(type(value) is not type(assignment[variable]) or value != assignment[variable]
               for variable, value in forced.items()):
            raise ValueError('comparison forced values contradict the verified witness')
        partition = [*forced, *case['not_forced'], *case['undetermined']]
        if len(partition) != len(set(partition)) or set(partition) != set(projection):
            raise ValueError('comparison forced, non-forced and undetermined variables must partition the projection')
        alternative = case['alternative_assignment']
        if alternative is not None:
            if not verify(request.model, alternative, request.cases[name])['valid']:
                raise ValueError('comparison alternative witness failed independent model verification')
            if (case['uniqueness'] != 'MULTIPLE' or
                    not any(alternative[v] != assignment[v] for v in projection) or
                    any(alternative[v] != value for v, value in forced.items())):
                raise ValueError('comparison alternative witness contradicts its uniqueness or forced values')
        elif case['uniqueness'] == 'MULTIPLE':
            raise ValueError('a multiple-solution comparison case requires its alternative witness')
        if case['uniqueness'] == 'UNIQUE' and (set(forced) != set(projection) or not case['complete']):
            raise ValueError('a unique comparison case must preserve all projected forced values')
    complete = all(case['complete'] for case in cases.values())
    status = 'EXECUTION_ERROR' if failures else 'COMPLETE' if complete else 'PARTIAL'
    if result['failed_cases'] != failures or result['complete'] != complete or result['status'] != status:
        raise ValueError('comparison aggregate status does not match its cases')
    # The pair list is redundant evidence. Reject a contradictory/mixed list
    # instead of silently using one of two incompatible versions of a result.
    expected_observations = []
    names = list(cases)
    for index, left in enumerate(names):
        for right in names[index + 1:]:
            a, b = cases[left], cases[right]
            if a['status'] != 'SAT' or b['status'] != 'SAT':
                continue
            for variable, value in a['forced_values'].items():
                if variable in b['forced_values'] and b['forced_values'][variable] != value:
                    expected_observations.append({'variable': variable,
                        'predictions': {left: value, right: b['forced_values'][variable]},
                        'observation_acquired': False})
    expected_rows = sorted(catalog.canonical_json(row) for row in expected_observations)
    supplied_rows = sorted(catalog.canonical_json(row) for row in result['distinguishing_observations'])
    if supplied_rows != expected_rows:
        raise ValueError('comparison pair predictions contradict its case results')
    return cases


def from_comparison(comparison_inputs: dict, comparison: dict, observables: list[dict],
                    criterion: str = 'separation_per_cost') -> dict:
    """Bind a supplied comparison to explicit observable tests, without solving.

    Pass the returned rank_inputs directly to experiment.rank_tests. Receipt and
    witness consistency is checked; execution and forced-value proofs are not
    authenticated or re-executed.
    """
    from . import catalog
    from .ledger import _validate_receipt

    supplied = {'comparison_inputs': comparison_inputs, 'comparison': comparison,
                'observables': observables, 'criterion': criterion}
    if len(catalog.canonical_json(supplied)) > 1_000_000:
        raise ValueError('comparison adapter input exceeds 1 MB admission limit')
    p = FromComparisonInput.model_validate(supplied)
    normalized = p.comparison_inputs.model_dump(mode='json')
    envelope = {key: getattr(p.comparison, key) for key in ('operation_id', 'result', 'receipt')}
    receipt = envelope['receipt']
    observations = receipt.get('runtime_observations')
    if type(observations) is not dict:
        raise ValueError('comparison receipt must contain runtime observations')
    op = catalog.REGISTRY['hypotheses.compare']
    if op.version != '3':
        raise ValueError('comparison adapter supports only hypotheses.compare contract version 3')
    identity = {'operation_id': op.operation_id, 'operation_version': op.version,
                'implementation': receipt.get('preparation_implementation_fingerprint'),
                'inputs': normalized, 'runtime_mode': observations.get('before')}

    def digest(value):
        return hashlib.sha256(catalog.canonical_json(value).encode('utf8')).hexdigest()

    _validate_receipt(op.operation_id, normalized, envelope, identity, digest(identity),
                      expected_implementation=receipt.get('implementation_fingerprint'))
    cases = _comparison_cases(p.comparison_inputs, envelope['result'])
    if len({item.id for item in p.observables}) != len(p.observables):
        raise ValueError('observable test IDs must be distinct')
    if len({item.variable for item in p.observables}) != len(p.observables):
        raise ValueError('observe each model variable at most once')
    tests = []
    for item in p.observables:
        if item.variable not in p.comparison_inputs.model.projection:
            raise ValueError('observable variables must belong to the comparison answer projection')
        sort = p.comparison_inputs.model.variables[item.variable].sort
        predictions = {}
        for name, case in cases.items():
            value = case['forced_values'].get(item.variable)
            predictions[name] = (sort + ':' + catalog.canonical_json(value)
                                 if case['status'] == 'SAT' and item.variable in case['forced_values'] else None)
        tests.append({'id': item.id, 'question': item.question, 'source': item.source,
                      'cost': item.cost, 'predictions': predictions})
    hypotheses = [{'id': name, 'mechanism': 'Explicit comparison case ' + name,
                   'source': 'hypotheses.compare request ' + receipt['inputs_sha256'], 'weight': 1}
                  for name in sorted(cases)]
    rank_inputs = Input(hypotheses=hypotheses, tests=tests, criterion=p.criterion).model_dump(mode='json')
    comparison_identity = {key: receipt[key] for key in (
        'operation_version', 'experiment_key', 'implementation_fingerprint',
        'preparation_implementation_fingerprint', 'inputs_sha256', 'result_sha256')}
    comparison_identity.update(operation_id=op.operation_id, model_sha256=digest(normalized['model']),
                               cases_sha256=digest(normalized['cases']), case_ids=sorted(cases))
    evidence = {name: {'status': case['status'], 'execution_status': case['execution_status'],
                      'complete': case['complete'], 'requested_hypotheses': list(p.comparison_inputs.cases[name]),
                      'predicted_variables': sorted(case['forced_values'])}
                for name, case in cases.items()}
    return {'rank_inputs': rank_inputs, 'comparison_identity': comparison_identity,
            'case_evidence': evidence, 'observation_acquired': False,
            'outcome_encoding': 'Model sort followed by colon and canonical JSON scalar (int:1, bool:true, bv8:1). String-valued symbolic domains are unsupported.',
            'scope': 'Conditional predictions from a supplied comparison envelope under the current operation contract. Request/result hashes, case metadata and SAT witnesses are checked for consistency; receipts are not authenticated and forced-value proofs are not re-executed. All cases remain in the ranking. Non-SAT cases and unresolved variables receive unknown predictions; established forced values in partial SAT cases are retained. Equal weight per supplied case; duplicate/correlated assumptions are not deduplicated. Observable sources and costs are caller claims; no observation was acquired or hypothesis eliminated.'}


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
    return [make('experiment.from_comparison', 'Turn compared hypotheses into observable tests',
                 'Bind a hypotheses.compare envelope to caller-specified observation sources and costs; produce typed predictions for experiment.rank_tests.',
                 FromComparisonInput, from_comparison, 'hypotheses compare forced observations prediction bridge rank next experiment',
                 'Receipt and witness consistency for conditional test inputs, not authenticated execution, a new forced-value proof or acquired evidence.',
                 'Comparison contract version 3 only; 2-8 case IDs of 1-64 characters, 128 observable variables, existing 1 MB input/output admission bounds; no solver work.',
                 rank_inputs=Input, comparison_identity=ComparisonIdentity,
                 case_evidence=dict[str, CaseEvidence], observation_acquired=Literal[False],
                 outcome_encoding=str, scope=str),
            make('experiment.rank_tests', 'Choose a discriminating next experiment',
                 'Rank explicit predicted disagreements per cost; preserve missing predictions instead of treating them as evidence.',
                 Input, rank_tests, 'next experiment information gain hypothesis discriminate prioritize uncertainty',
                 'Conditional test ranking, not proof or measured chance of solving.', '64 hypotheses,128 tests; finite pairwise accounting.',
                 example={'hypotheses': [{'id': 'a', 'mechanism': 'row reading', 'source': 'clue'}, {'id': 'b', 'mechanism': 'column reading', 'source': 'clue'}],
                          'tests': [{'id': 'first-symbol', 'question': 'What is the first extracted symbol?', 'cost': 1, 'predictions': {'a': 'A', 'b': 'B'}, 'source': 'model predictions'}]},
                 tests=list[dict], next_test_id=str | None, status=str, weight_convention=str, scope=str)]
