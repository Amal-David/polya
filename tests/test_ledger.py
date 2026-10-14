import copy
import hashlib
from itertools import chain, repeat
import random
import sqlite3
from unittest.mock import patch

import pytest
from polya.ledger import Ledger, _coverage_ranges, _gaps
from polya import catalog


def test_persistent_retraction_reaches_transitive_dependents(tmp_path):
    db=str(tmp_path/'case.sqlite')
    with Ledger(db) as log:
        a=log.append('observation',{'glyph':'3'})
        b=log.append('hypothesis',{'meaning':'index'},dependencies=[a])
        c=log.append('experiment',{'status':'UNKNOWN'},dependencies=[b])
        d=log.append('observation',{'independent':'not retracted'})
    with Ledger(db) as log:
        log.append('retraction',{'reason':'original image shows 8'},retracts=a)
        statuses={e['id']:e['review_status'] for e in log.snapshot()['events']}
        assert statuses[a]=='RETRACTED'
        assert statuses[b]==statuses[c]=='REVIEW_REQUIRED'
        assert statuses[d]=='RECORDED'
        assert not log.snapshot()['authenticated']
        assert len(log.events())==5


def test_events_are_detached_and_bad_dependencies_rollback():
    with Ledger(':memory:') as log:
        payload={'text':'original'};a=log.append('observation',payload);payload['text']='changed'
        assert log.events()[0]['payload']['text']=='original'
        with pytest.raises(ValueError): log.append('hypothesis',{},dependencies=['missing'])
        assert len(log.events())==1
        with pytest.raises(ValueError): log.append('observation',{},retracts=a)
        log.append('review',{},dependencies=[a])
        assert len(log.events())==2


def test_detects_edited_body_and_hash_chain():
    with Ledger(':memory:') as log:
        log.append('observation',{'x':1})
        log.connection.execute("UPDATE evidence_events SET body=replace(body,'\"x\":1','\"x\":2')")
        log.connection.commit()
        with pytest.raises(ValueError,match='integrity'): log.snapshot()
        with pytest.raises(ValueError): log.append('review',{})


def plan_fixture(*, invalid=False, target=b'A'):
    """Four independently known ordinals: A, A, BE, BE; or invalid,A,invalid,BE."""
    return {
        'sources': [{'id': 'bits', 'kind': 'bits', 'value': '01000001' + ('1' if invalid else ''),
                     'source': 'synthetic exact bit source'}],
        'nodes': [
            {'id': 'polarity', 'alternatives': [
                {'operation_id': 'bits.invert', 'bindings': {'text': {'node': 'bits', 'field': 'value'}},
                 'inputs': {'invert': invert}, 'rationale': 'explicit polarity'}
                for invert in (False, True)]},
            {'id': 'packed', 'alternatives': [
                {'operation_id': 'bits.pack', 'bindings': {'text': {'node': 'polarity', 'field': 'text'}},
                 'inputs': {'bit_order': 'msb', 'tail': tail}, 'rationale': 'explicit tail convention'}
                for tail in ('reject', 'drop')]},
        ],
        'candidate': {'node': 'packed', 'field': 'hex'},
        'target': {'kind': 'direct', 'target': {'kind': 'sha256',
                   'value': hashlib.sha256(target).hexdigest(), 'source': 'synthetic byte commitment'}},
    }


def page(log, plan, *, start=0, plan_id=None, **budgets):
    return log.run('mechanism.plan_scan', {
        'plan': plan, 'start': start, 'expected_plan_id': plan_id, **budgets})


def test_execute_record_restart_gaps_overlaps_and_exact_plan(tmp_path):
    db = str(tmp_path / 'execution.sqlite')
    plan = plan_fixture()
    with Ledger(db) as log:
        first = page(log, plan, max_trials=2)
        plan_id = first['result']['plan_id']
        second = page(log, plan, start=1, plan_id=plan_id, max_trials=2)
        changed = copy.deepcopy(plan)
        changed['sources'][0]['source'] = 'different caller interpretation'
        other = page(log, changed, max_trials=1)
        assert other['result']['plan_id'] != plan_id
    with Ledger(db) as log:
        coverage = log.plan_coverage(plan_id)
        assert coverage['recipe_count'] == 4
        assert coverage['attempted_ranges'] == coverage['valid_ranges'] == [[0, 3]]
        assert coverage['matched_ranges'] == [[0, 2]]
        assert coverage['negative_ranges'] == [[2, 3]]
        assert coverage['gaps'] == coverage['unresolved_ranges'] == [[3, 4]]
        assert coverage['overlap_ranges'] == [[1, 2]]
        assert coverage['counts']['attempted'] == 3
        assert coverage['counts']['overlap'] == 1
        assert not coverage['complete']
        assert {entry['event_id'] for entry in coverage['pages']} == {
            first['ledger_event_id'], second['ledger_event_id']}
        assert all(len(entry['receipt_sha256']) == 64 for entry in coverage['pages'])
        final = page(log, plan, start=3, plan_id=plan_id)
        assert not final['result']['complete']  # A resumed suffix alone is incomplete.
        coverage = log.plan_coverage(plan_id)
        assert coverage['complete'] and coverage['gaps'] == []
        assert coverage['counts']['valid'] == 4
        assert not coverage['independently_reproduced']
        assert not coverage['authenticated']


def test_invalid_terminal_trials_never_become_negative_coverage():
    with Ledger(':memory:') as log:
        execution = page(log, plan_fixture(invalid=True))
        assert execution['result']['complete']
        coverage = log.plan_coverage(execution['result']['plan_id'])
        assert coverage['attempted_ranges'] == [[0, 4]]
        assert coverage['valid_ranges'] == [[1, 2], [3, 4]]
        assert coverage['invalid_ranges'] == coverage['unresolved_ranges'] == [[0, 1], [2, 3]]
        assert coverage['matched_ranges'] == [[1, 2]]
        assert coverage['negative_ranges'] == [[3, 4]]
        assert coverage['gaps'] == [] and not coverage['complete']


def test_completed_valid_negatives_have_scoped_negative_conclusion():
    with Ledger(':memory:') as log:
        execution = page(log, plan_fixture(target=b'absent'))
        coverage = log.plan_coverage(execution['result']['plan_id'])
        assert coverage['complete']
        assert coverage['negative_ranges'] == [[0, 4]]
        assert coverage['conclusion'] == 'NO_TARGET_MATCH_IN_COMPLETED_PLAN'


def test_nonapplicable_reading_is_invalid_not_a_valid_negative():
    plan = {'sources': [{'id': 'raw', 'kind': 'bytes', 'value': '41', 'source': 'synthetic'}],
            'candidate': {'node': 'raw', 'field': 'value'},
            'target': {'kind': 'direct', 'target': {'kind': 'p2pkh',
                       'value': '1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH', 'compressed': True,
                       'source': 'synthetic test target'}}}
    with Ledger(':memory:') as log:
        execution = page(log, plan)
        assert execution['result']['trials'][0]['outcome'] == 'READING_NOT_APPLICABLE'
        coverage = log.plan_coverage(execution['result']['plan_id'])
        assert coverage['invalid_ranges'] == [[0, 1]]
        assert coverage['valid_ranges'] == coverage['negative_ranges'] == []
        assert not coverage['complete'] and coverage['conclusion'] == 'INCONCLUSIVE'


def test_work_interruption_persists_no_unfinished_trial(tmp_path):
    db = str(tmp_path / 'partial.sqlite')
    with Ledger(db) as log:
        execution = page(log, plan_fixture(), max_work=1)
        plan_id = execution['result']['plan_id']
        assert execution['result']['stop'] == execution['result']['next_start'] == 0
        assert execution['result']['termination_reason'] == 'work_limit'
    with Ledger(db) as log:
        coverage = log.plan_coverage(plan_id)
        assert coverage['attempted_ranges'] == []
        assert coverage['gaps'] == coverage['unresolved_ranges'] == [[0, 4]]
        assert len(coverage['pages']) == 1
        assert not coverage['complete']


def test_deadline_records_only_completed_prefix_and_can_resume():
    with Ledger(':memory:') as log:
        # First trial: initial clock, loop, three kernel boundary pairs, final
        # clock. The next loop times out before touching the second ordinal.
        with patch('polya.plans.time.monotonic', side_effect=chain([0] * 9, repeat(100))):
            execution = page(log, plan_fixture())
        result = execution['result']
        assert result['stop'] == result['next_start'] == 1
        assert result['termination_reason'] == 'time_limit'
        assert log.plan_coverage(result['plan_id'])['valid_ranges'] == [[0, 1]]
        page(log, plan_fixture(), start=1, plan_id=result['plan_id'])
        assert log.plan_coverage(result['plan_id'])['complete']


def test_retracted_and_dependent_pages_are_excluded_after_restart(tmp_path):
    db = str(tmp_path / 'retracted.sqlite')
    with Ledger(db) as log:
        source = log.append('observation', {'source': 'test scan'})
        hypothesis = log.append('hypothesis', {'polarity': 'explicit'}, dependencies=[source])
        first = log.run('mechanism.plan_scan', {'plan': plan_fixture(), 'max_trials': 2},
                        dependencies=[hypothesis])
        plan_id = first['result']['plan_id']
        second = page(log, plan_fixture(), start=2, plan_id=plan_id)
        log.append('retraction', {'reason': 'source withdrawn'}, retracts=source)
        log.append('retraction', {'reason': 'page withdrawn'}, retracts=second['ledger_event_id'])
    with Ledger(db) as log:
        coverage = log.plan_coverage(plan_id)
        assert coverage['attempted_ranges'] == []
        assert coverage['gaps'] == [[0, 4]]
        assert set(coverage['excluded_event_ids']) == {first['ledger_event_id'], second['ledger_event_id']}
        assert [row['review_status'] for row in coverage['pages']] == ['REVIEW_REQUIRED', 'RETRACTED']


def test_generic_appended_receipt_claims_do_not_count_as_execution():
    with Ledger(':memory:') as log:
        execution = page(log, plan_fixture(), max_trials=1)
        event = log.events()[0]
        # Even a perfect copy of a real execution payload remains a caller claim.
        forged = log.append('experiment', event['payload'])
        log.append('retraction', {}, retracts=execution['ledger_event_id'])
        coverage = log.plan_coverage(execution['result']['plan_id'])
        assert coverage['valid_ranges'] == []
        assert forged not in {row['event_id'] for row in coverage['pages']}


def test_generic_execution_preserves_envelope_and_compacts_persistent_result():
    with Ledger(':memory:') as log:
        execution = log.run('text.profile', {'text': 'a' * 2000})
        assert execution['operation_id'] == 'text.profile'
        assert execution['result']['codepoint_length'] == 2000
        payload = log.events()[0]['payload']
        assert payload['receipt'] == execution['receipt']
        assert payload['page'] is None and 'result' not in payload and 'inputs' not in payload
        execution['receipt']['inputs_sha256'] = 'changed after recording'
        assert log.events()[0]['payload']['receipt']['inputs_sha256'] != 'changed after recording'


@pytest.mark.parametrize('mutation', [
    lambda e: e.update(operation_id='text.profile'),
    lambda e: e['receipt'].update(inputs_sha256='0' * 64),
    lambda e: e['receipt'].update(result_sha256='0' * 64),
    lambda e: e['receipt'].update(experiment_key='0' * 64),
    lambda e: e['receipt'].update(operation_version='not-the-version'),
    lambda e: e['receipt'].update(independently_reproduced=True),
    lambda e: e['receipt'].update(scope='Authenticated external proof'),
    lambda e: e['receipt'].update(unexpected_assertion=True),
    lambda e: e['receipt']['runtime_observations'].update(changed=True),
    lambda e: e['result'].update(stop=100),
])
def test_wrong_or_tampered_execution_receipts_are_not_recorded(mutation):
    original_run = catalog.run

    def tamper(operation_id, inputs):
        envelope = original_run(operation_id, inputs)
        mutation(envelope)
        return envelope

    with Ledger(':memory:') as log, patch('polya.catalog.run', side_effect=tamper):
        with pytest.raises(ValueError, match='receipt'):
            page(log, plan_fixture())
        assert log.events() == []
        assert log.connection.execute('SELECT count(*) FROM execution_events').fetchone()[0] == 0


@pytest.mark.parametrize('mutation', [
    lambda result: result.update(plan_id='0' * 64),
    lambda result: result['coverage'].update(completed=100),
    lambda result: result['trials'][0].update(ordinal=3),
    lambda result: result['trials'][0].update(choices=[999, 0]),
    lambda result: result['trials'][0].update(choices=[True, 0]),
    lambda result: result['trials'][0].update(choices=[0]),
    lambda result: result['trials'][0].update(outcome='UNKNOWN'),
    lambda result: result['trials'][0].update(error={'message': 'unexpected'}),
    lambda result: result['trials'][0].update(candidate_sha256=None),
    lambda result: result['matches'][0].update(choices=[999, 0]),
    lambda result: result['matches'][0].update(candidate_hex='42'),
    lambda result: result.update(matches=[]),
    lambda result: result.update(next_start=2),
])
def test_even_rehashed_results_cannot_invent_page_coverage(mutation):
    original_run = catalog.run

    def tamper(operation_id, inputs):
        envelope = original_run(operation_id, inputs)
        mutation(envelope['result'])
        envelope['receipt']['result_sha256'] = hashlib.sha256(
            catalog.canonical_json(envelope['result']).encode()).hexdigest()
        return envelope

    with Ledger(':memory:') as log, patch('polya.catalog.run', side_effect=tamper):
        with pytest.raises(ValueError):
            page(log, plan_fixture())
        assert log.events() == []


@pytest.mark.parametrize('stale_field', ['implementation', 'runtime_mode'])
def test_coherently_rehashed_stale_receipt_cannot_import_old_execution(stale_field):
    original_run = catalog.run

    def stale_execution(operation_id, inputs):
        operation, normalized, identity, _ = catalog.prepare(operation_id, inputs)
        envelope = original_run(operation_id, inputs)
        stale_identity = copy.deepcopy(identity)
        if stale_field == 'implementation':
            stale_identity['implementation'] = 'f' * 64
            envelope['result']['plan_id'] = hashlib.sha256(catalog.canonical_json({
                'schema': 1, 'implementation': stale_identity['implementation'],
                'plan': normalized['plan']}).encode()).hexdigest()
        else:
            stale_identity['runtime_mode']['utf8_mode'] = not identity['runtime_mode']['utf8_mode']
        stale_key = hashlib.sha256(catalog.canonical_json(stale_identity).encode()).hexdigest()
        envelope['receipt'] = catalog.make_receipt(
            operation, normalized, stale_identity, stale_key, envelope['result'])
        return envelope

    with Ledger(':memory:') as log, patch('polya.catalog.run', side_effect=stale_execution):
        with pytest.raises(ValueError, match='receipt'):
            page(log, plan_fixture())
        assert log.events() == []
        assert log.connection.execute('SELECT count(*) FROM execution_events').fetchone()[0] == 0


def test_execution_index_tampering_is_detected():
    with Ledger(':memory:') as log:
        execution = page(log, plan_fixture())
        log.connection.execute("UPDATE execution_events SET payload_sha256=?", ('0' * 64,))
        log.connection.commit()
        with pytest.raises(ValueError, match='integrity'):
            log.plan_coverage(execution['result']['plan_id'])


def test_missing_dependency_prevents_execution_and_unknown_plan_is_explicit():
    with Ledger(':memory:') as log, patch('polya.catalog.run') as execute:
        with pytest.raises(ValueError, match='dependency'):
            log.run('text.profile', {'text': 'a'}, dependencies=['missing'])
        execute.assert_not_called()
        unknown = log.plan_coverage('a' * 64)
        assert not unknown['known'] and unknown['recipe_count'] is None
        assert unknown['gaps'] is None and unknown['unresolved_ranges'] is None
        assert not unknown['complete']
        with pytest.raises(ValueError, match='plan_id'):
            log.plan_coverage('not-an-id')


def test_raised_operation_error_produces_no_execution_evidence():
    with Ledger(':memory:') as log, patch('polya.catalog.run', side_effect=RuntimeError('failed')):
        with pytest.raises(RuntimeError, match='failed'):
            page(log, plan_fixture())
        assert log.events() == []


def test_outcome_interval_sweep_against_independent_exhaustive_small_oracle():
    rng = random.Random(8301)
    for _ in range(100):
        ranges = [sorted(rng.sample(range(21), 2)) for _ in range(rng.randrange(30))]
        depths = [sum(start <= ordinal < stop for start, stop in ranges) for ordinal in range(20)]
        for minimum in (1, 2):
            merged = _coverage_ranges(ranges, minimum)
            expanded = {ordinal for start, stop in merged for ordinal in range(start, stop)}
            assert expanded == {ordinal for ordinal, depth in enumerate(depths) if depth >= minimum}
            assert all(left[1] < right[0] for left, right in zip(merged, merged[1:]))
        union = _coverage_ranges(ranges)
        gaps = {ordinal for start, stop in _gaps(union, 20) for ordinal in range(start, stop)}
        assert gaps == {ordinal for ordinal, depth in enumerate(depths) if depth == 0}


def test_event_and_execution_index_are_committed_atomically():
    with Ledger(':memory:') as log:
        log.connection.execute(
            "CREATE TRIGGER reject_execution BEFORE INSERT ON execution_events "
            "BEGIN SELECT RAISE(ABORT, 'injected index write failure'); END")
        with pytest.raises(sqlite3.IntegrityError, match='injected'):
            page(log, plan_fixture())
        assert log.events() == []
        assert log.connection.execute('SELECT count(*) FROM execution_events').fetchone()[0] == 0
        log.append('observation', {'after_failure': True})
        assert len(log.events()) == 1


def test_excessive_coverage_fragmentation_is_explicitly_bounded():
    with Ledger(':memory:') as log:
        execution = page(log, plan_fixture(invalid=True))
        with patch('polya.ledger.MAX_QUERY_RANGES', 1):
            with pytest.raises(ValueError, match='stored-range limit'):
                log.plan_coverage(execution['result']['plan_id'])
