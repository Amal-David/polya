"""Durable generic executions, interruption boundaries and fresh exact reruns."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import sqlite3
from unittest.mock import patch

import pytest

from polya import catalog
from polya.ledger import Ledger
from polya.symbolic import Budget
from polya.workspace import Workspace


def recorded_events(root):
    with Ledger(root / 'history.sqlite') as ledger:
        events = ledger.snapshot()['events']
        indexed = dict(ledger.connection.execute('SELECT event_id,payload_sha256 FROM execution_events'))
    return events, indexed


def test_restart_retains_exact_normalized_request_response_and_dependencies(tmp_path):
    with Ledger(tmp_path / 'history.sqlite') as ledger:
        source = ledger.append('observation', {'text': 'synthetic ABBA'})
    request = {'text': 'LXFOPVEFRNHR', 'key': 'LEMON', 'variant': 'vigenere'}
    with Workspace(tmp_path) as workspace:
        result = workspace.run_recorded('cipher.polyalphabetic', request, dependencies=[source])
        assert result['result']['text'] == 'ATTACKATDAWN'
        raw_request = workspace.get(result['request_ref'])
        raw_response = workspace.get(result['response_ref'])
        assert hashlib.sha256(raw_request).hexdigest() == result['request_ref'][7:]
        assert hashlib.sha256(raw_response).hexdigest() == result['response_ref'][7:]
        assert set(json.loads(raw_response)) == {'operation_id', 'result', 'receipt'}
        request['text'] = 'changed after recording'
        result['result']['text'] = 'changed returned value'
    with Workspace(tmp_path) as workspace:
        saved = workspace.load_recorded(result['ledger_event_id'])
        assert saved['inputs']['text'] == 'LXFOPVEFRNHR'
        assert saved['envelope']['result']['text'] == 'ATTACKATDAWN'
        assert saved['dependencies'] == [source]
        assert saved['review_status'] == 'RECORDED'
        assert saved['replay_of'] is None and not saved['independently_reproduced']
        normalized = catalog.prepare('cipher.polyalphabetic', {
            'text': 'LXFOPVEFRNHR', 'key': 'LEMON', 'variant': 'vigenere'})[1]
        assert saved['inputs'] == normalized
        assert json.loads(raw_request) == {'operation_id': 'cipher.polyalphabetic', 'inputs': normalized}
        saved['inputs']['text'] = 'changed loaded value'
        assert workspace.load_recorded(result['ledger_event_id'])['inputs']['text'] == 'LXFOPVEFRNHR'
    events, indexed = recorded_events(tmp_path)
    execution = events[-1]
    assert execution['id'] in indexed
    assert execution['payload']['recorded_run']['request_ref'] == result['request_ref']
    assert execution['payload']['recorded_run']['response_ref'] == result['response_ref']


def test_replay_reexecutes_kernel_and_adds_fresh_dependent_event_without_cache(tmp_path):
    with Workspace(tmp_path) as workspace, patch('polya.catalog.run', wraps=catalog.run) as execute:
        original = workspace.run_recorded('text.profile', {'text': 'ABBA'})
        replay = workspace.replay_recorded(original['ledger_event_id'])
        assert execute.call_count == 2
        assert replay['result']['counts'] == {'A': 2, 'B': 2}
        assert replay['ledger_event_id'] != original['ledger_event_id']
        assert replay['replay']['status'] == 'MATCH'
        assert not replay['receipt']['independently_reproduced']
        assert not replay['replay']['independently_reproduced']
        assert replay['request_ref'] == original['request_ref']
        assert replay['response_ref'] == original['response_ref']
        assert workspace.connection.execute('SELECT count(*) FROM artifacts').fetchone()[0] == 2
        saved = workspace.load_recorded(replay['ledger_event_id'])
        assert saved['dependencies'] == [original['ledger_event_id']]
        assert saved['replay_of'] == original['ledger_event_id']
    events, indexed = recorded_events(tmp_path)
    assert len(events) == len(indexed) == 2


def test_partial_budget_and_canonical_case_order_survive_restart_and_replay(tmp_path):
    inputs = {'model': {'variables': {'x': {'values': [0, 1]}}},
              'cases': {'z': [], 'a': []}, 'backend': 'reference', 'max_checks': 1}
    with Workspace(tmp_path) as workspace:
        original = workspace.run_recorded('hypotheses.compare', inputs)
    with Workspace(tmp_path) as workspace:
        saved = workspace.load_recorded(original['ledger_event_id'])
        assert list(saved['inputs']['cases']) == ['a', 'z']
        assert saved['inputs']['max_checks'] == 1
        assert saved['inputs']['timeout_ms'] == 5000
        replay = workspace.replay_recorded(original['ledger_event_id'])
        for envelope in (original, saved['envelope'], replay):
            assert envelope['result']['status'] == 'PARTIAL'
            assert not envelope['result']['complete']
            assert envelope['result']['cases']['a']['status'] == 'SAT'
            assert envelope['result']['cases']['z']['status'] == 'UNKNOWN'
            assert envelope['result']['cases']['z']['reason'] == 'shared_budget'


def test_complete_negative_retains_its_model_scope(tmp_path):
    with Workspace(tmp_path) as workspace:
        original = workspace.run_recorded('symbolic.solve', {
            'model': {'variables': {'x': {'values': []}}}, 'backend': 'reference'})
        saved = workspace.load_recorded(original['ledger_event_id'])
    assert saved['envelope']['result']['status'] == 'UNSAT'
    assert saved['envelope']['result']['complete']
    assert saved['envelope']['result']['solutions'] == []
    assert 'supplied model' in saved['envelope']['result']['scope']


def test_alias_is_recorded_under_its_canonical_id(tmp_path):
    with Workspace(tmp_path) as workspace:
        result = workspace.run_recorded('symbols.to_bits', {'text': 'ABBA', 'zero': 'A', 'one': 'B'})
        saved = workspace.load_recorded(result['ledger_event_id'])
    assert saved['operation_id'] == saved['envelope']['operation_id'] == 'bits.from_symbols'
    assert saved['envelope']['result']['text'] == '0110'


def test_varying_elapsed_statistics_report_exact_mismatch_without_invalidating_solution(tmp_path, monkeypatch):
    stats = Budget.stats
    elapsed = iter((1.0, 2.0))

    def deterministic_elapsed(self):
        return {**stats(self), 'elapsed_ms': next(elapsed)}

    monkeypatch.setattr(Budget, 'stats', deterministic_elapsed)
    with Workspace(tmp_path) as workspace:
        original = workspace.run_recorded('symbolic.solve', {
            'model': {'variables': {'x': {'values': [4]}}}, 'backend': 'reference'})
        replay = workspace.replay_recorded(original['ledger_event_id'])
    assert original['result']['solutions'] == replay['result']['solutions'] == [{'x': 4}]
    assert original['result']['complete'] and replay['result']['complete']
    assert replay['replay']['status'] == 'MISMATCH'
    assert 'timing/statistics' in replay['replay']['scope']
    assert 'not by itself a semantic failure' in replay['replay']['scope']


def test_first_run_backend_identity_transition_uses_final_identity_for_replay(tmp_path, monkeypatch):
    op = catalog.REGISTRY['text.profile']
    mode = {'loaded': False}

    def load_then_execute(**inputs):
        result = op.kernel(**inputs)
        mode['loaded'] = True
        return result

    monkeypatch.setitem(catalog.REGISTRY, 'text.profile', replace(op, kernel=load_then_execute))
    monkeypatch.setattr(catalog, 'implementation_fingerprint', lambda: ('b' if mode['loaded'] else 'a') * 64)
    monkeypatch.setattr(catalog, 'execution_mode', lambda: {'test_backend_loaded': mode['loaded']})
    with Workspace(tmp_path) as workspace:
        original = workspace.run_recorded('text.profile', {'text': 'ABBA'})
        assert original['receipt']['implementation_changed']
        assert original['receipt']['runtime_observations']['changed']
        replay = workspace.replay_recorded(original['ledger_event_id'])
    assert replay['receipt']['preparation_implementation_fingerprint'] == 'b' * 64
    assert not replay['receipt']['implementation_changed']
    assert replay['replay']['status'] == 'MATCH'


@pytest.mark.parametrize('changed', ['implementation', 'operation_version', 'runtime'])
def test_incompatible_replay_is_blocked_before_execution_but_history_remains_readable(tmp_path, monkeypatch, changed):
    with Workspace(tmp_path) as workspace:
        original = workspace.run_recorded('text.profile', {'text': 'ABBA'})
        if changed == 'implementation':
            monkeypatch.setattr(catalog, 'implementation_fingerprint', lambda: '0' * 64)
        elif changed == 'operation_version':
            op = catalog.REGISTRY['text.profile']
            monkeypatch.setitem(catalog.REGISTRY, 'text.profile', replace(op, version='future'))
        else:
            mode = catalog.execution_mode()
            monkeypatch.setattr(catalog, 'execution_mode', lambda: {**mode, 'utf8_mode': not mode['utf8_mode']})
        assert workspace.load_recorded(original['ledger_event_id'])['envelope']['result']['counts'] == {'A': 2, 'B': 2}
        with patch('polya.catalog.run') as execute, pytest.raises(ValueError, match='incompatible'):
            workspace.replay_recorded(original['ledger_event_id'])
        execute.assert_not_called()
    assert len(recorded_events(tmp_path)[0]) == 1


@pytest.mark.parametrize('direct', [False, True])
def test_retractions_and_dependency_invalidation_remain_visible_and_block_replay(tmp_path, direct):
    with Ledger(tmp_path / 'history.sqlite') as ledger:
        source = ledger.append('observation', {'text': 'synthetic ABBA'})
    with Workspace(tmp_path) as workspace:
        original = workspace.run_recorded('text.profile', {'text': 'ABBA'}, dependencies=[source])
        replay = workspace.replay_recorded(original['ledger_event_id'])
        with Ledger(tmp_path / 'history.sqlite') as ledger:
            ledger.append('retraction', {'reason': 'fixture withdrawn'},
                          retracts=original['ledger_event_id'] if direct else source)
        assert workspace.load_recorded(original['ledger_event_id'])['review_status'] == ('RETRACTED' if direct else 'REVIEW_REQUIRED')
        assert workspace.load_recorded(replay['ledger_event_id'])['review_status'] == 'REVIEW_REQUIRED'
        with patch('polya.catalog.run') as execute, pytest.raises(ValueError, match='retracted or review-required'):
            workspace.replay_recorded(original['ledger_event_id'])
        execute.assert_not_called()


def test_caller_appended_copy_is_not_an_execution_and_legacy_runs_have_no_payloads(tmp_path):
    with Workspace(tmp_path) as workspace:
        original = workspace.run_recorded('text.profile', {'text': 'ABBA'})
        with Ledger(tmp_path / 'history.sqlite') as ledger:
            payload = ledger.events()[0]['payload']
            claimed = ledger.append('experiment', deepcopy(payload))
            compact = ledger.run('text.profile', {'text': 'ABBA'})
        with pytest.raises(ValueError, match='internally recorded'):
            workspace.load_recorded(claimed)
        with pytest.raises(ValueError, match='no supported durable'):
            workspace.load_recorded(compact['ledger_event_id'])
        assert workspace.load_recorded(original['ledger_event_id'])['review_status'] == 'RECORDED'


@pytest.mark.parametrize('which', ['request_ref', 'response_ref'])
@pytest.mark.parametrize('damage', ['replace', 'delete'])
def test_missing_or_corrupted_payload_cannot_be_loaded_or_replayed(tmp_path, which, damage):
    with Workspace(tmp_path) as workspace:
        original = workspace.run_recorded('text.profile', {'text': 'ABBA'})
        digest = original[which][7:]
        if damage == 'replace':
            workspace.connection.execute('UPDATE artifacts SET body=? WHERE sha=?', (b'{}', digest))
        else:
            workspace.connection.execute('DELETE FROM artifacts WHERE sha=?', (digest,))
        workspace.connection.commit()
        with patch('polya.catalog.run') as execute:
            with pytest.raises((ValueError, KeyError)):
                workspace.load_recorded(original['ledger_event_id'])
            with pytest.raises((ValueError, KeyError)):
                workspace.replay_recorded(original['ledger_event_id'])
        execute.assert_not_called()


def test_execution_index_tampering_rejects_the_record(tmp_path):
    with Workspace(tmp_path) as workspace:
        original = workspace.run_recorded('text.profile', {'text': 'ABBA'})
        with Ledger(tmp_path / 'history.sqlite') as ledger:
            ledger.connection.execute('UPDATE execution_events SET payload_sha256=?', ('0' * 64,))
            ledger.connection.commit()
        with pytest.raises(ValueError, match='integrity'):
            workspace.load_recorded(original['ledger_event_id'])


@pytest.mark.parametrize('operation_id,inputs,dependencies', [
    ('text.profile', {'text': 5}, None),
    ('missing.operation', {}, None),
    ('text.profile', {'text': 'A'}, ['missing']),
    ('text.profile', {'text': 'A'}, ['duplicate', 'duplicate']),
])
def test_bad_request_or_dependencies_fail_before_execution(tmp_path, operation_id, inputs, dependencies):
    with Workspace(tmp_path) as workspace, patch('polya.catalog.run') as execute:
        with pytest.raises(ValueError):
            workspace.run_recorded(operation_id, inputs, dependencies=dependencies)
        execute.assert_not_called()
        assert workspace.connection.execute('SELECT count(*) FROM artifacts').fetchone()[0] == 0
    assert recorded_events(tmp_path) == ([], {})


@pytest.mark.parametrize('event_id', ['', '../../history.sqlite', None, '0' * 32])
def test_load_accepts_only_known_local_execution_ids(tmp_path, event_id):
    with Workspace(tmp_path) as workspace, pytest.raises(ValueError):
        workspace.load_recorded(event_id)


def test_exhausted_artifact_count_and_byte_capacity_reject_before_execution(tmp_path, monkeypatch):
    with Workspace(tmp_path) as workspace:
        for i in range(512):
            workspace.put(str(i).encode())
        with patch('polya.catalog.run') as execute, pytest.raises(ValueError, match='capacity'):
            workspace.run_recorded('text.profile', {'text': 'ABBA'})
        execute.assert_not_called()
    with Workspace(tmp_path / 'bytes') as workspace:
        monkeypatch.setattr('polya.workspace.MAX_TOTAL', 1)
        with patch('polya.catalog.run') as execute, pytest.raises(ValueError, match='capacity'):
            workspace.run_recorded('text.profile', {'text': 'ABBA'})
        execute.assert_not_called()
    assert recorded_events(tmp_path) == ([], {})


def test_final_response_capacity_failure_leaves_only_unreferenced_request(tmp_path, monkeypatch):
    monkeypatch.setattr('polya.workspace.MAX_TOTAL', 1000)
    with Workspace(tmp_path) as workspace:
        with pytest.raises(ValueError, match='capacity'):
            workspace.run_recorded('text.profile', {'text': 'ABBA'})
        assert workspace.connection.execute('SELECT count(*) FROM artifacts').fetchone()[0] == 1
    assert recorded_events(tmp_path) == ([], {})


def test_request_wrapper_size_is_checked_before_execution(tmp_path, monkeypatch):
    monkeypatch.setattr('polya.workspace.MAX_ARTIFACT', 40)
    with Workspace(tmp_path) as workspace, patch('polya.catalog.run') as execute:
        with pytest.raises(ValueError, match='recorded request'):
            workspace.run_recorded('text.profile', {'text': 'ABBA'})
        execute.assert_not_called()
    assert recorded_events(tmp_path) == ([], {})


def test_complete_response_size_includes_receipt_and_publishes_nothing_if_too_large(tmp_path, monkeypatch):
    monkeypatch.setattr('polya.workspace.MAX_ARTIFACT', 1000)
    with Workspace(tmp_path) as workspace:
        with pytest.raises(ValueError, match='response including its receipt'):
            workspace.run_recorded('text.profile', {'text': 'ABBA'})
        assert workspace.connection.execute('SELECT count(*) FROM artifacts').fetchone()[0] == 0
    assert recorded_events(tmp_path) == ([], {})


def test_interruption_between_durable_blobs_never_publishes_execution(tmp_path):
    with Workspace(tmp_path) as workspace:
        put = workspace.put
        calls = 0

        def interrupt_second(data):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise KeyboardInterrupt('injected between blob commits')
            return put(data)

        with patch.object(workspace, 'put', side_effect=interrupt_second), pytest.raises(KeyboardInterrupt):
            workspace.run_recorded('text.profile', {'text': 'ABBA'})
        assert workspace.connection.execute('SELECT count(*) FROM artifacts').fetchone()[0] == 1
        assert recorded_events(tmp_path) == ([], {})
        result = workspace.run_recorded('text.profile', {'text': 'ABBA'})
        assert workspace.load_recorded(result['ledger_event_id'])['envelope']['result']['counts'] == {'A': 2, 'B': 2}


def test_ledger_commit_failure_leaves_durable_blobs_but_no_execution_or_index(tmp_path):
    with Ledger(tmp_path / 'history.sqlite') as ledger:
        ledger.connection.execute(
            "CREATE TRIGGER reject_record BEFORE INSERT ON execution_events "
            "BEGIN SELECT RAISE(ABORT, 'injected index failure'); END")
    with Workspace(tmp_path) as workspace:
        with pytest.raises(sqlite3.IntegrityError, match='injected'):
            workspace.run_recorded('text.profile', {'text': 'ABBA'})
        assert workspace.connection.execute('SELECT count(*) FROM artifacts').fetchone()[0] == 2
    assert recorded_events(tmp_path) == ([], {})


@pytest.mark.parametrize('failure', ['raised', 'tampered_receipt', 'cache_envelope'])
def test_failed_or_invalid_executor_response_is_not_recorded(tmp_path, failure):
    execute = catalog.run

    def failed_response(operation_id, inputs):
        if failure == 'raised':
            raise RuntimeError('injected failure')
        envelope = execute(operation_id, inputs)
        if failure == 'tampered_receipt':
            envelope['receipt']['inputs_sha256'] = '0' * 64
        else:
            envelope['cache_hit'] = True
        return envelope

    with Workspace(tmp_path) as workspace, patch('polya.catalog.run', side_effect=failed_response):
        with pytest.raises((RuntimeError, ValueError)):
            workspace.run_recorded('text.profile', {'text': 'ABBA'})
        assert workspace.connection.execute('SELECT count(*) FROM artifacts').fetchone()[0] == 0
    assert recorded_events(tmp_path) == ([], {})
