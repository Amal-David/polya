"""Explicit local investigation history, separate from execution caches and tools.

Hash chaining detects accidental edits; it is not authentication against someone
who can rewrite the database. Recording evidence never certifies its truth.
"""
from __future__ import annotations
import hashlib
from math import prod
import re
import sqlite3
import time
import uuid
from . import catalog
from .catalog import canonical_json
from .jsonio import loads

KINDS = {'observation','hypothesis','experiment','review','retraction'}
ZERO = '0'*64
PLAN_OPERATION = 'mechanism.plan_scan'
VALID_OUTCOMES = frozenset({'TARGET_MATCH', 'NO_TARGET_MATCH', 'NO_VALID_PADDING'})
INVALID_OUTCOMES = frozenset({'INVALID_RECIPE_INPUT', 'READING_NOT_APPLICABLE'})
MAX_QUERY_RANGES = 100000


def _sha(value) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def _digest(value) -> bool:
    return type(value) is str and re.fullmatch(r'[0-9a-f]{64}', value) is not None


def _validate_receipt(operation_id: str, inputs: dict, envelope: dict,
                      identity: dict, key: str) -> dict:
    """Check the locally obtained envelope before discarding its large result.

    These are consistency checks, not authentication. The public entry point
    executes catalog.run itself; callers cannot import arbitrary receipts.
    """
    op = catalog.REGISTRY[operation_id]
    if type(envelope) is not dict or envelope.get('operation_id') != operation_id:
        raise ValueError('execution receipt operation mismatch')
    receipt = envelope.get('receipt')
    if type(receipt) is not dict or type(envelope.get('result')) is not dict:
        raise ValueError('execution receipt and result must be objects')
    observations = receipt.get('runtime_observations')
    if (type(observations) is not dict or
            type(observations.get('before')) is not dict or
            type(observations.get('after')) is not dict or
            type(observations.get('changed')) is not bool or
            observations['changed'] != (observations['before'] != observations['after'])):
        raise ValueError('execution receipt runtime observations are inconsistent')
    if (not _digest(receipt.get('implementation_fingerprint')) or
            not _digest(receipt.get('preparation_implementation_fingerprint'))):
        raise ValueError('execution receipt implementation fingerprint is invalid')
    # identity/key came from our preparation before calling the executor, not
    # from fields inside its returned receipt. A coherent receipt from an old
    # implementation/runtime must not import stale coverage as a new execution.
    expected = catalog.make_receipt(
        op, inputs, identity, key, envelope['result'],
        runtime_after=observations['after'],
        final_fingerprint=receipt['implementation_fingerprint'])
    if canonical_json(receipt) != canonical_json(expected):
        raise ValueError('execution receipt does not match the executed request/result')
    if not observations['changed'] and (receipt['implementation_fingerprint'] !=
                                         receipt['preparation_implementation_fingerprint']):
        raise ValueError('execution receipt implementation changed without a runtime change')
    if op.result:
        op.result.model_validate(envelope['result'])
    return receipt


def _append_range(ranges: list[list[int]], start: int, stop: int) -> None:
    if start == stop:
        return
    if ranges and ranges[-1][1] == start:
        ranges[-1][1] = stop
    else:
        ranges.append([start, stop])


def _page_summary(inputs: dict, result: dict, receipt: dict) -> dict:
    """Derive coverage from terminal trial rows, never from supplied counts."""
    plan_id = _sha({'schema': 1,
                    'implementation': receipt['preparation_implementation_fingerprint'],
                    'plan': inputs['plan']})
    sizes = [len(node['alternatives']) for node in inputs['plan']['nodes']]
    total = prod(sizes)
    start, stop = result.get('start'), result.get('stop')
    if (result.get('plan_id') != plan_id or type(result.get('recipe_count')) is not int or
            result['recipe_count'] != total or type(start) is not int or type(stop) is not int or
            start != inputs['start'] or not 0 <= start <= stop <= total):
        raise ValueError('execution plan identity or range does not match its request')
    trials = result.get('trials')
    if (type(trials) is not list or len(trials) != stop - start or
            len(trials) > inputs['max_trials']):
        raise ValueError('execution coverage does not match terminal trial rows')
    ranges = {outcome: [] for outcome in sorted(VALID_OUTCOMES | INVALID_OUTCOMES)}
    match_ordinals = []
    for ordinal, trial in enumerate(trials, start):
        if (type(trial) is not dict or type(trial.get('ordinal')) is not int or
                trial['ordinal'] != ordinal or trial.get('outcome') not in ranges):
            raise ValueError('execution trial ordinals/outcomes are invalid')
        remaining, choices = ordinal, []
        for size in reversed(sizes):
            remaining, choice = divmod(remaining, size)
            choices.append(choice)
        choices.reverse()
        if (type(trial.get('choices')) is not list or
                any(type(choice) is not int for choice in trial['choices']) or
                trial['choices'] != choices):
            raise ValueError('execution trial choices do not match their plan ordinal')
        outcome = trial['outcome']
        if outcome == 'INVALID_RECIPE_INPUT':
            if type(trial.get('error')) is not dict or trial.get('candidate_sha256') is not None:
                raise ValueError('invalid execution trial must retain its error without a candidate hash')
        elif trial.get('error') is not None or not _digest(trial.get('candidate_sha256')):
            raise ValueError('terminal execution trial must retain its candidate hash without an error')
        _append_range(ranges[outcome], ordinal, ordinal + 1)
        if outcome == 'TARGET_MATCH':
            match_ordinals.append(ordinal)
    matches = result.get('matches')
    if (type(matches) is not list or any(type(row) is not dict for row in matches) or
            [row.get('ordinal') for row in matches] != match_ordinals or
            len(matches) > inputs['max_matches']):
        raise ValueError('execution matches do not match terminal trial rows')
    for match in matches:
        trial = trials[match['ordinal'] - start]
        if any(canonical_json(match.get(key)) != canonical_json(trial.get(key))
               for key in ('ordinal', 'choices', 'outcome', 'error', 'candidate_sha256')):
            raise ValueError('execution match disagrees with its terminal trial')
        candidate = match.get('candidate_hex')
        if (type(candidate) is not str or len(candidate) > 32768 or
                re.fullmatch(r'(?:[0-9a-fA-F]{2})*', candidate) is None or
                hashlib.sha256(bytes.fromhex(candidate)).hexdigest() != trial['candidate_sha256']):
            raise ValueError('execution match bytes do not match their candidate hash')
    exhausted = stop == total
    if (type(result.get('complete')) is not bool or
            result['complete'] != (start == 0 and exhausted) or
            type(result.get('range_exhausted')) is not bool or
            result['range_exhausted'] != exhausted or
            result.get('next_start') != (None if exhausted else stop) or
            type(result.get('termination_reason')) is not str):
        raise ValueError('execution continuation does not match its terminal range')
    invalid = sum(end - begin for outcome in INVALID_OUTCOMES
                  for begin, end in ranges[outcome])
    derived = {'start': start, 'stop': stop, 'total': total, 'completed': len(trials),
               'invalid': invalid, 'valid': len(trials) - invalid}
    coverage = result.get('coverage')
    if (type(coverage) is not dict or
            any(type(coverage.get(key)) is not int or coverage[key] != value
                for key, value in derived.items())):
        raise ValueError('execution coverage counters do not match terminal trial rows')
    return {'plan_id': plan_id, 'recipe_count': total, 'start': start, 'stop': stop,
            'next_start': result['next_start'], 'complete': result['complete'],
            'range_exhausted': exhausted, 'termination_reason': result['termination_reason'],
            'outcome_ranges': ranges, 'coverage': derived}


def _coverage_ranges(ranges: list[list[int]], minimum: int = 1) -> list[list[int]]:
    """Sweep interval endpoints without allocating one item per recipe."""
    points = {}
    for start, stop in ranges:
        if start == stop:
            continue
        points[start] = points.get(start, 0) + 1
        points[stop] = points.get(stop, 0) - 1
    result, depth, previous = [], 0, None
    for point, delta in sorted(points.items()):
        if previous is not None and depth >= minimum:
            _append_range(result, previous, point)
        depth += delta
        previous = point
    return result


def _gaps(ranges: list[list[int]], total: int) -> list[list[int]]:
    result, cursor = [], 0
    for start, stop in ranges:
        _append_range(result, cursor, start)
        cursor = stop
    _append_range(result, cursor, total)
    return result


class Ledger:
    def __init__(self, path: str):
        self.connection = sqlite3.connect(path, timeout=10)
        self.connection.execute('CREATE TABLE IF NOT EXISTS evidence_events (seq INTEGER PRIMARY KEY, id TEXT UNIQUE NOT NULL, body TEXT NOT NULL, previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL)')
        self.connection.execute('CREATE TABLE IF NOT EXISTS execution_events (event_id TEXT PRIMARY KEY, payload_sha256 TEXT NOT NULL)')
        self.connection.commit()

    def events(self) -> list[dict]:
        rows = self.connection.execute('SELECT seq,id,body,previous_hash,event_hash FROM evidence_events ORDER BY seq LIMIT 10001').fetchall()
        if len(rows)>10000:
            raise ValueError('ledger exceeds 10000-event prototype limit')
        previous, result = ZERO, []
        for expected, (seq, event_id, body, prior, digest) in enumerate(rows, 1):
            expected_hash=hashlib.sha256((previous+'\n'+body).encode()).hexdigest()
            event=loads(body)
            if seq!=expected or prior!=previous or digest!=expected_hash or event['id']!=event_id:
                raise ValueError('ledger integrity check failed')
            result.append(event)
            previous=digest
        return result

    def append(self, kind: str, payload: dict, *, dependencies: list[str] | None = None,
               retracts: str | None = None) -> str:
        """Record a caller claim; this never contributes execution coverage."""
        return self._append(kind, payload, dependencies=dependencies, retracts=retracts)

    def _append(self, kind: str, payload: dict, *, dependencies: list[str] | None = None,
                retracts: str | None = None, executed: bool = False) -> str:
        if type(kind) is not str or kind not in KINDS or type(payload) is not dict:
            raise ValueError('explicit event kind and object payload required')
        deps=[] if dependencies is None else dependencies
        if type(deps) is not list or len(deps)>32 or any(type(d) is not str for d in deps) or len(set(deps))!=len(deps):
            raise ValueError('dependencies must be up to 32 distinct event IDs')
        if (kind=='retraction') != (retracts is not None):
            raise ValueError('only retraction events require a retracts ID')
        if len(canonical_json(payload).encode())>65536:
            raise ValueError('event payload exceeds 64 KiB')
        try:
            self.connection.execute('BEGIN IMMEDIATE')
            events=self.events()
            known={e['id']:e for e in events}
            if len(events)>=10000: raise ValueError('ledger event limit')
            if any(d not in known for d in deps): raise ValueError('dependency does not exist')
            if retracts is not None and (retracts not in known or known[retracts]['kind']=='retraction'):
                raise ValueError('retraction must target an existing non-retraction event')
            event_id=uuid.uuid4().hex
            event={'id':event_id,'kind':kind,'payload':payload,'dependencies':deps,
                   'retracts':retracts,'recorded_at_ns':time.time_ns()}
            body=canonical_json(event)
            row=self.connection.execute('SELECT event_hash FROM evidence_events ORDER BY seq DESC LIMIT 1').fetchone()
            prior=row[0] if row else ZERO
            digest=hashlib.sha256((prior+'\n'+body).encode()).hexdigest()
            self.connection.execute('INSERT INTO evidence_events VALUES (?,?,?,?,?)',(len(events)+1,event_id,body,prior,digest))
            if executed:
                self.connection.execute('INSERT INTO execution_events VALUES (?,?)',
                                        (event_id, _sha(payload)))
            self.connection.commit()
            return event_id
        except Exception:
            self.connection.rollback()
            raise

    def run(self, operation_id: str, inputs: dict, *,
            dependencies: list[str] | None = None) -> dict:
        """Execute and atomically record a receipt plus compact plan coverage.

        Returns the ordinary catalog envelope with ``ledger_event_id`` added.
        Full results and candidate bytes are returned but not persisted. A failed
        or interrupted Python call records nothing; a returned partial page
        records only its terminal trials. Restart uses the same database path.
        """
        # Reject malformed dependencies and a corrupt/full ledger before doing
        # potentially expensive work; _append repeats these checks under lock.
        deps = [] if dependencies is None else dependencies
        if (type(deps) is not list or len(deps) > 32 or
                any(type(dep) is not str for dep in deps) or len(set(deps)) != len(deps)):
            raise ValueError('dependencies must be up to 32 distinct event IDs')
        deps = list(deps)
        events = self.events()
        known = {event['id'] for event in events}
        if any(dep not in known for dep in deps):
            raise ValueError('dependency does not exist')
        if len(events) >= 10000:
            raise ValueError('ledger event limit')
        if type(operation_id) is not str or operation_id not in catalog.REGISTRY:
            raise ValueError('unknown operation_id')
        # Own the request snapshot. Caller/kernel mutation cannot rewrite the
        # request whose hash is checked after execution.
        _, normalized, identity, key = catalog.prepare(operation_id, inputs)
        envelope = catalog.run(operation_id, loads(canonical_json(normalized)))
        receipt = _validate_receipt(operation_id, normalized, envelope, identity, key)
        page = (_page_summary(normalized, envelope['result'], receipt)
                if operation_id == PLAN_OPERATION else None)
        payload = {'execution_schema': 1, 'operation_id': operation_id,
                   'receipt': receipt, 'receipt_sha256': _sha(receipt), 'page': page}
        event_id = self._append('experiment', payload, dependencies=list(deps), executed=True)
        return {**envelope, 'ledger_event_id': event_id}

    def plan_coverage(self, plan_id: str) -> dict:
        """Query actual recorded pages for one exact plan, excluding invalidation.

        Counts are unique ordinal counts, not sums of page counters. ``gaps``
        are unvisited ordinals; ``unresolved_ranges`` also includes invalid or
        contradictory trials. Overlap never establishes independent reproduction.
        Unknown plans have no inferred recipe count or complement ranges.
        """
        if not _digest(plan_id):
            raise ValueError('plan_id must be a lowercase SHA256 digest')
        # Read both tables from one SQLite snapshot. A concurrent append must
        # not look like an orphaned execution index between two SELECTs.
        owned_transaction = not self.connection.in_transaction
        try:
            if owned_transaction:
                self.connection.execute('BEGIN')
            events = self.snapshot()['events']
            indexed = dict(self.connection.execute(
                'SELECT event_id,payload_sha256 FROM execution_events LIMIT 10001').fetchall())
            if owned_transaction:
                self.connection.commit()
        except Exception:
            if owned_transaction:
                self.connection.rollback()
            raise
        if len(indexed) > 10000 or not set(indexed) <= {event['id'] for event in events}:
            raise ValueError('execution index integrity check failed')
        pages, excluded, total = [], [], None
        attempts = []
        by_outcome = {outcome: [] for outcome in VALID_OUTCOMES | INVALID_OUTCOMES}
        range_count = 0
        for event in events:
            if event['id'] not in indexed:
                continue
            payload = event['payload']
            if (event['kind'] != 'experiment' or payload.get('execution_schema') != 1 or
                    _sha(payload) != indexed[event['id']] or
                    _sha(payload.get('receipt')) != payload.get('receipt_sha256')):
                raise ValueError('execution index/receipt integrity check failed')
            page = payload.get('page')
            if page is None or page.get('plan_id') != plan_id:
                continue
            if payload['operation_id'] != PLAN_OPERATION:
                raise ValueError('execution plan operation mismatch')
            if total is not None and page['recipe_count'] != total:
                raise ValueError('execution plan recipe counts disagree')
            total = page['recipe_count']
            active = event['review_status'] == 'RECORDED'
            pages.append({'event_id': event['id'], 'review_status': event['review_status'],
                          'active': active, 'start': page['start'], 'stop': page['stop'],
                          'termination_reason': page['termination_reason'],
                          'receipt_sha256': payload['receipt_sha256'],
                          'inputs_sha256': payload['receipt']['inputs_sha256'],
                          'result_sha256': payload['receipt']['result_sha256'],
                          'experiment_key': payload['receipt']['experiment_key']})
            if not active:
                excluded.append(event['id'])
                continue
            attempts.append([page['start'], page['stop']])
            for outcome, ranges in page['outcome_ranges'].items():
                range_count += len(ranges)
                if range_count > MAX_QUERY_RANGES:
                    raise ValueError('coverage query exceeds 100000 stored-range limit')
                by_outcome[outcome].extend(ranges)
        outcome_ranges = {outcome: _coverage_ranges(ranges)
                          for outcome, ranges in by_outcome.items()}
        attempted = _coverage_ranges(attempts)
        valid = _coverage_ranges([item for outcome in VALID_OUTCOMES
                                  for item in outcome_ranges[outcome]])
        invalid = _coverage_ranges([item for outcome in INVALID_OUTCOMES
                                    for item in outcome_ranges[outcome]])
        negatives = _coverage_ranges(outcome_ranges['NO_TARGET_MATCH'] +
                                     outcome_ranges['NO_VALID_PADDING'])
        matches = outcome_ranges['TARGET_MATCH']
        overlaps = _coverage_ranges(attempts, minimum=2)
        conflicts = _coverage_ranges([item for ranges in outcome_ranges.values()
                                      for item in ranges], minimum=2)
        gaps = None if total is None else _gaps(attempted, total)
        unresolved = (None if total is None else
                      _coverage_ranges(_gaps(valid, total) + conflicts))
        ranges = {'attempted_ranges': attempted, 'valid_ranges': valid,
                  'invalid_ranges': invalid, 'negative_ranges': negatives,
                  'matched_ranges': matches, 'overlap_ranges': overlaps,
                  'conflict_ranges': conflicts}
        counts = {name.removesuffix('_ranges'): sum(stop - start for start, stop in intervals)
                  for name, intervals in ranges.items()}
        complete = total is not None and not unresolved
        return {'plan_id': plan_id, 'known': total is not None, 'recipe_count': total,
                **ranges, 'gaps': gaps, 'unresolved_ranges': unresolved,
                'counts': counts, 'complete': complete,
                'conclusion': ('INCONCLUSIVE' if conflicts else 'TARGET_MATCH' if matches else
                               'NO_TARGET_MATCH_IN_COMPLETED_PLAN' if complete else 'INCONCLUSIVE'),
                'pages': pages, 'excluded_event_ids': excluded,
                'authenticated': False, 'independently_reproduced': False,
                'scope': 'Actual internally executed terminal trials for this exact plan ID. '
                         'Generic appended claims and retracted/dependency-invalid pages are excluded. '
                         'Invalid trials and interruptions are not valid negatives. '
                         'Outcome counts can overlap across disagreeing reruns; conflicts remain unresolved. '
                         'Overlapping pages are not independent reproduction. Receipt/hash checks '
                         'detect inconsistent edits, not an attacker able to rewrite the database. '
                         'At most 100000 stored outcome ranges per query.'}

    def snapshot(self) -> dict:
        events=self.events()
        retracted={e['retracts'] for e in events if e['kind']=='retraction'}
        affected=set(retracted)
        # Dependencies only point backwards, so a single chronological pass suffices.
        for event in events:
            if any(d in affected for d in event['dependencies']): affected.add(event['id'])
        return {'events':[dict(e,review_status='RETRACTED' if e['id'] in retracted else
                              'REVIEW_REQUIRED' if e['id'] in affected else 'RECORDED') for e in events],
                'scope':'Recorded claims only. Dependency invalidation requests review; it does not refute a puzzle.',
                'authenticated':False}

    def close(self): self.connection.close()
    def __enter__(self): return self
    def __exit__(self,*_): self.close()
