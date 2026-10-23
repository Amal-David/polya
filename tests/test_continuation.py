"""Source-bound continuation, using only synthetic nonfinancial fixtures."""
import base64
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from unittest.mock import patch

import pytest

from polya import catalog
from polya.casepacks import encoded
from polya.workflows import Continuation


def fixture(*, text='01000001', encoding='utf8', target='AB', tails=('reject', 'drop')):
    raw = text.encode('utf8') if encoding == 'utf8' else bytes.fromhex(text)
    source = {'id': 'source', 'kind': 'bits' if encoding == 'utf8' else 'bytes',
              'value': text, 'source': 'synthetic exact source'}
    nodes = [] if encoding == 'hex' else [
        {'id': 'polarity', 'alternatives': [
            {'operation_id': 'bits.invert', 'bindings': {'text': {'node': 'source', 'field': 'value'}},
             'inputs': {'invert': invert}, 'rationale': 'two explicit conventions'}
            for invert in (False, True)]},
        {'id': 'bytes', 'alternatives': [
            {'operation_id': 'bits.pack', 'bindings': {'text': {'node': 'polarity', 'field': 'text'}},
             'inputs': {'bit_order': 'msb', 'tail': tail}, 'rationale': 'declared tail convention'}
            for tail in tails]},
    ]
    case = {'id': 'synthetic-continuation', 'question': 'Which declared equality relation holds?',
            'artifacts': [{'id': 'evidence', 'encoding': encoding, 'content': text,
                           'sha256': hashlib.sha256(raw).hexdigest(), 'source': 'synthetic bytes'}]}
    plan = {'sources': [source], 'nodes': nodes,
            'candidate': {'node': 'source' if encoding == 'hex' else 'bytes',
                          'field': 'value' if encoding == 'hex' else 'hex'},
            'target': {'kind': 'equality_pattern', 'target': {'pattern': target,
                       'source': 'synthetic equality convention', 'digest': 'none', 'representation': 'bytes'}}}
    return case, plan, {'source': 'evidence'}


def prepare(workflow, **kwargs):
    return workflow.prepare(*fixture(**kwargs))


def control_fixture():
    case, plan, bindings = fixture()
    case['calibrations'] = [{'id': 'control', 'operation_id': 'text.encode',
        'inputs': {'codec': 'ascii'}, 'artifact_bindings': {'text': 'evidence'},
        'output_field': 'hex', 'expected_value_sha256': hashlib.sha256(encoded(b'01000001'.hex())).hexdigest(),
        'source': 'synthetic known control'}]
    return case, plan, bindings


def test_stored_sources_run_through_actual_local_entrypoint_and_restart(tmp_path):
    case, plan, bindings = fixture()
    with Continuation(tmp_path) as workflow:
        handle = workflow.workspace.put(case['artifacts'][0]['content'].encode())
        case['artifacts'][0]['content'] = None
        del plan['sources'][0]['value']
        plan['sources'][0]['artifact_ref'] = handle
        ticket = workflow.prepare(case, plan, bindings)
        observed = []
        real_run = catalog.run
        def capture(operation_id, inputs):
            observed.append(deepcopy(inputs['plan']['sources'][0]))
            return real_run(operation_id, inputs)
        with patch.object(catalog, 'run', capture):
            first = workflow.run_page(ticket['ticket_ref'], max_trials=2)
        assert observed[0]['value'] == '01000001'
        assert 'artifact_ref' not in observed[0]
        assert first['result']['coverage']['completed'] == 2
        assert not workflow.handoff(ticket['ticket_ref'])['local_coverage']['complete']
    with Continuation(tmp_path) as workflow:
        second = workflow.run_page(ticket['ticket_ref'], max_trials=2)
        assert second['result']['start'] == 2
        handoff = workflow.handoff(ticket['ticket_ref'])
        assert handoff['local_coverage']['complete']
        assert handoff['local_coverage']['conclusion'] == 'NO_TARGET_MATCH_IN_COMPLETED_PLAN'
        assert handoff['counts']['generated_ordinals'] == 4
        assert handoff['counts']['unique_candidates'] is None
        assert handoff['counts']['unique_completed_ordinals'] == 4
        assert handoff['independent_replay'] == 'NOT_ESTABLISHED'


def test_inline_and_stored_requests_are_identical_and_caller_mutation_isolated(tmp_path):
    case, plan, bindings = fixture()
    with Continuation(tmp_path / 'inline') as first:
        ticket = first.prepare(case, plan, bindings)
        inputs = first.request(ticket['ticket_ref'])
        plan['sources'][0]['value'] = '11111111'
        case['artifacts'][0]['content'] = 'bad'
        bindings['source'] = 'bad'
        inputs['plan']['sources'][0]['value'] = '00000000'
        original_inputs = first.request(ticket['ticket_ref'])
    with Continuation(tmp_path / 'stored') as second:
        other_case, other_plan, other_bindings = fixture()
        handle = second.workspace.put(b'01000001')
        other_case['artifacts'][0]['content'] = None
        other_plan['sources'][0].pop('value')
        other_plan['sources'][0]['artifact_ref'] = handle
        stored = second.prepare(other_case, other_plan, other_bindings)
        assert second.request(stored['ticket_ref']) == original_inputs


def test_actual_mismatched_source_is_rejected_before_execution(tmp_path):
    case, plan, bindings = fixture()
    plan['sources'][0]['value'] = '01000010'
    with Continuation(tmp_path) as workflow, patch.object(catalog, 'run') as run:
        with pytest.raises(ValueError, match='actual plan source bytes'):
            workflow.prepare(case, plan, bindings)
        run.assert_not_called()


def test_every_source_requires_matching_explicit_artifact_binding(tmp_path):
    case, plan, bindings = fixture()
    with Continuation(tmp_path) as workflow:
        for invalid in [{}, {'source': 'unknown'}, {'source': 'evidence', 'extra': 'evidence'}]:
            with pytest.raises(ValueError):
                workflow.prepare(case, plan, invalid)


def test_bytes_and_unicode_are_bound_as_exact_bytes_not_same_spelling(tmp_path):
    with Continuation(tmp_path) as workflow:
        ticket = prepare(workflow, text='c3a9', encoding='hex')
        result = workflow.run_page(ticket['ticket_ref'])
        assert result['result']['sources'][0]['length'] == 2
        bad_case, plan, bindings = fixture(text='c3a9', encoding='hex')
        bad_case['artifacts'][0].update(encoding='utf8', content='é')
        with pytest.raises(ValueError, match='actual plan source bytes'):
            workflow.prepare(bad_case, plan, bindings)


def test_missing_and_corrupt_artifacts_block_before_actual_execution(tmp_path):
    with Continuation(tmp_path) as workflow:
        ticket = prepare(workflow)
        sha = hashlib.sha256(b'01000001').hexdigest()
        workflow.workspace.connection.execute('DELETE FROM artifacts WHERE sha=?', (sha,))
        workflow.workspace.connection.commit()
        handoff = workflow.handoff(ticket['ticket_ref'])
        assert not handoff['inspection']['ready']
        assert handoff['inspection']['artifacts'][0]['status'] == 'MISSING_REQUIRED'
        with patch.object(catalog, 'run') as run, pytest.raises(ValueError, match='missing or corrupt'):
            workflow.run_page(ticket['ticket_ref'])
        run.assert_not_called()


def test_missing_optional_artifact_still_blocks_when_it_is_an_actual_plan_source(tmp_path):
    case, plan, bindings = fixture()
    case['artifacts'][0]['required'] = False
    with Continuation(tmp_path) as workflow:
        ticket = workflow.prepare(case, plan, bindings)
        workflow.run_page(ticket['ticket_ref'])
        sha = hashlib.sha256(b'01000001').hexdigest()
        workflow.workspace.connection.execute('DELETE FROM artifacts WHERE sha=?', (sha,))
        workflow.workspace.connection.commit()
        report = workflow.handoff(ticket['ticket_ref'])
        assert report['inspection']['ready']  # Optional for a generic case, required by this bound plan.
        assert not report['inspection']['bound_sources_ready'] and not report['completed_negative']
        with pytest.raises(ValueError, match='bound plan source artifact is missing'):
            workflow.run_page(ticket['ticket_ref'])
        workflow.workspace.put(b'01000001')
        workflow.workspace.connection.execute('UPDATE artifacts SET body=? WHERE sha=?', (b'bad', sha))
        workflow.workspace.connection.commit()
        with patch.object(catalog, 'run') as run, pytest.raises(ValueError, match='content/hash mismatch'):
            workflow.run_page(ticket['ticket_ref'])
        run.assert_not_called()


def test_overlapping_pages_deduplicate_and_retractions_invalidate_dependents(tmp_path):
    with Continuation(tmp_path) as workflow:
        ticket = prepare(workflow)
        first = workflow.run_page(ticket['ticket_ref'], start=0, max_trials=2)
        second = workflow.run_page(ticket['ticket_ref'], start=1, max_trials=2,
                                   dependencies=[first['ledger_event_id']])
        workflow.run_page(ticket['ticket_ref'], start=3, max_trials=1,
                          dependencies=[second['ledger_event_id']])
        covered = workflow.handoff(ticket['ticket_ref'])['local_coverage']
        assert covered['complete'] and covered['counts']['attempted'] == 4
        assert covered['counts']['overlap'] == 1
        workflow.ledger.append('retraction', {'reason': 'synthetic source correction'},
                               retracts=first['ledger_event_id'])
        covered = workflow.handoff(ticket['ticket_ref'])['local_coverage']
        assert not covered['complete'] and covered['counts']['attempted'] == 0
        assert covered['gaps'] == [[0, 4]]
        assert len(covered['excluded_event_ids']) == 3


def test_invalid_trials_are_never_completed_negatives(tmp_path):
    with Continuation(tmp_path) as workflow:
        ticket = prepare(workflow, text='010000011')
        workflow.run_page(ticket['ticket_ref'])
        coverage = workflow.handoff(ticket['ticket_ref'])['local_coverage']
        assert coverage['counts']['attempted'] == 4
        assert coverage['counts']['invalid'] == 2
        assert coverage['unresolved_ranges'] == [[0, 1], [2, 3]]
        assert not coverage['complete'] and coverage['conclusion'] == 'INCONCLUSIVE'


def test_conflicting_completed_pages_remain_unresolved(tmp_path):
    with Continuation(tmp_path) as workflow:
        ticket = prepare(workflow)
        workflow.run_page(ticket['ticket_ref'])
        operation = catalog.REGISTRY['mechanism.plan_scan']
        def conflicting_kernel(**inputs):
            result = operation.kernel(**inputs)
            trial = result['trials'][0]
            trial['outcome'] = 'TARGET_MATCH'
            result['matches'] = [{**trial, 'candidate_hex': '41'}]
            return result
        with patch.dict(catalog.REGISTRY, {'mechanism.plan_scan': replace(operation, kernel=conflicting_kernel)}):
            workflow.run_page(ticket['ticket_ref'], start=0)
        coverage = workflow.handoff(ticket['ticket_ref'])['local_coverage']
        assert coverage['conflict_ranges'] == [[0, 1]]
        assert not coverage['complete'] and coverage['conclusion'] == 'INCONCLUSIVE'


def test_unicode_source_is_transmitted_without_normalization(tmp_path):
    text = 'e\u0301'
    raw = text.encode('utf8')
    case = {'id': 'unicode', 'question': 'Preserve Unicode units and bytes', 'artifacts': [
        {'id': 'text', 'encoding': 'utf8', 'content': text,
         'sha256': hashlib.sha256(raw).hexdigest(), 'source': 'synthetic decomposed text'}]}
    plan = {'sources': [{'id': 'source', 'kind': 'symbols', 'value': text, 'source': 'exact source'}],
            'nodes': [{'id': 'encoded', 'alternatives': [{'operation_id': 'text.encode',
                'bindings': {'text': {'node': 'source', 'field': 'value'}},
                'inputs': {'codec': 'utf-8'}, 'rationale': 'explicit UTF-8, no normalization'}]}],
            'candidate': {'node': 'encoded', 'field': 'hex'},
            'target': {'kind': 'equality_pattern', 'target': {'pattern': 'ABC', 'source': 'three distinct bytes',
                       'digest': 'none', 'representation': 'bytes'}}}
    with Continuation(tmp_path) as workflow:
        ticket = workflow.prepare(case, plan, {'source': 'text'})
        envelope = workflow.run_page(ticket['ticket_ref'])
        assert envelope['result']['sources'][0]['length'] == 2  # codepoints
        assert envelope['result']['matches'][0]['candidate_hex'] == raw.hex()  # three bytes


def test_interruption_records_no_page_and_explicit_budget_stop_resumes(tmp_path):
    with Continuation(tmp_path) as workflow:
        ticket = prepare(workflow)
        with patch.object(catalog, 'run', side_effect=KeyboardInterrupt), pytest.raises(KeyboardInterrupt):
            workflow.run_page(ticket['ticket_ref'])
        assert workflow.handoff(ticket['ticket_ref'])['local_coverage']['counts']['attempted'] == 0
        stopped = workflow.run_page(ticket['ticket_ref'], max_work=1)
        assert stopped['result']['stop'] == 0
        assert not workflow.handoff(ticket['ticket_ref'])['local_coverage']['complete']
        assert workflow.run_page(ticket['ticket_ref'])['result']['start'] == 0
        assert workflow.handoff(ticket['ticket_ref'])['local_coverage']['complete']


def test_ticket_cannot_override_plan_and_implementation_change_requires_reinspection(tmp_path):
    with Continuation(tmp_path) as workflow:
        ticket = prepare(workflow)
        with pytest.raises(ValueError, match='only declared page budgets'):
            workflow.run_page(ticket['ticket_ref'], plan={})
        with patch.object(catalog, 'implementation_fingerprint', return_value='a' * 64):
            assert not workflow.handoff(ticket['ticket_ref'])['runtime_compatible']
            with pytest.raises(ValueError, match='implementation or operation version'):
                workflow.run_page(ticket['ticket_ref'])


def test_remote_path_hydrates_actual_sources_and_never_imports_execution_coverage(tmp_path):
    observed = []
    def runner(operation_id, inputs):
        observed.append((operation_id, deepcopy(inputs)))
        return catalog.run(operation_id, inputs)
    with Continuation(tmp_path) as workflow:
        ticket = prepare(workflow)
        remote = workflow.run_remote_page(ticket['ticket_ref'], runner)
        assert observed[-1][1]['plan']['sources'][0]['value'] == '01000001'
        assert remote['state'] == 'REPLAY_REQUIRED' and not remote['certified_negative']
        handoff = workflow.handoff(ticket['ticket_ref'])
        assert handoff['local_coverage']['counts']['attempted'] == 0
        assert not handoff['local_coverage']['complete']
        replay = workflow.replay_remote_page(remote['event_id'])
        assert replay['status'] == 'MATCH' and not replay['independent_reproduction']
        assert workflow.handoff(ticket['ticket_ref'])['local_coverage']['complete']


def test_stored_handle_control_replay_uses_actual_remote_inputs(tmp_path):
    case, plan, bindings = fixture()
    case['calibrations'] = [{'id': 'control', 'operation_id': 'text.encode',
        'inputs': {'codec': 'ascii'}, 'artifact_bindings': {'text': 'evidence'},
        'output_field': 'hex', 'expected_value_sha256': hashlib.sha256(encoded(b'01000001'.hex())).hexdigest(),
        'source': 'synthetic ASCII encoding'}]
    seen = []
    def runner(operation_id, inputs):
        seen.append((operation_id, deepcopy(inputs)))
        return catalog.run(operation_id, inputs)
    with Continuation(tmp_path) as workflow:
        workflow.workspace.put(b'01000001')
        case['artifacts'][0]['content'] = None
        ticket = workflow.prepare(case, plan, bindings)
        report = workflow.replay_controls(ticket['ticket_ref'], runner=runner)
        assert report['status'] == 'CALIBRATED' and report['complete']
        assert report['execution_origin'] == 'remote_claim'
        assert seen == [('text.encode', {'codec': 'ascii', 'text': '01000001'})]
        assert workflow.handoff(ticket['ticket_ref'])['local_coverage']['counts']['attempted'] == 0
        local = workflow.replay_controls(ticket['ticket_ref'])
        assert local['status'] == 'CALIBRATED' and local['execution_origin'] == 'local'


def test_calibration_mismatch_and_partial_state_never_mean_negative(tmp_path):
    case, plan, bindings = fixture()
    case['calibrations'] = [{'id': 'bad-control', 'operation_id': 'text.encode',
        'inputs': {'codec': 'ascii'}, 'artifact_bindings': {'text': 'evidence'},
        'output_field': 'hex', 'expected_value_sha256': 'a' * 64, 'source': 'deliberately wrong control'}]
    with Continuation(tmp_path) as workflow:
        ticket = workflow.prepare(case, plan, bindings)
        report = workflow.replay_controls(ticket['ticket_ref'])
        assert report['status'] == 'CALIBRATION_FAILED'
        assert report['controls'][0]['status'] == 'REPLAY_MISMATCH'
        with patch('polya.workflows.time.monotonic', side_effect=[0, 2]):
            report = workflow.replay_controls(ticket['ticket_ref'], timeout_ms=1)
        assert report['status'] == 'PARTIAL' and not report['complete']
        assert workflow.handoff(ticket['ticket_ref'])['local_coverage']['counts']['attempted'] == 0


def test_stored_sources_execute_through_real_http_adapter_entrypoint(tmp_path):
    pytest.importorskip('mcp')
    from starlette.testclient import TestClient
    from deploy.server import create_app
    token = 'synthetic-continuation-token-at-least-32-characters'
    headers = {'Authorization': 'Bearer ' + token, 'Accept': 'application/json, text/event-stream'}
    submitted = []
    with TestClient(create_app(token, 'https://testserver')) as client:
        def runner(operation_id, inputs):
            submitted.append((operation_id, deepcopy(inputs)))
            response = client.post('/mcp', headers=headers, json={'jsonrpc': '2.0', 'id': 1,
                'method': 'tools/call', 'params': {'name': 'puzzle.run',
                'arguments': {'operation_id': operation_id, 'inputs': inputs}}})
            assert response.status_code == 200
            result = response.json()['result']
            assert not result['isError']
            return result['structuredContent']['data']
        with Continuation(tmp_path) as workflow:
            case, plan, bindings = fixture()
            handle = workflow.workspace.put(b'01000001')
            case['artifacts'][0]['content'] = None
            plan['sources'][0].pop('value')
            plan['sources'][0]['artifact_ref'] = handle
            ticket = workflow.prepare(case, plan, bindings)
            remote = workflow.run_remote_page(ticket['ticket_ref'], runner, max_trials=1)
            assert [operation for operation, _ in submitted] == ['mechanism.plan_inspect', 'mechanism.plan_scan']
            assert submitted[-1][1]['plan']['sources'][0]['value'] == '01000001'
            assert remote['envelope']['result']['coverage']['completed'] == 1
            assert workflow.handoff(ticket['ticket_ref'])['local_coverage']['counts']['attempted'] == 0


def test_preparation_retraction_prevents_further_calls(tmp_path):
    with Continuation(tmp_path) as workflow:
        ticket = prepare(workflow)
        workflow.ledger.append('retraction', {'reason': 'source convention withdrawn'}, retracts=ticket['event_id'])
        with patch.object(catalog, 'run') as run, pytest.raises(ValueError, match='retracted or requires review'):
            workflow.run_page(ticket['ticket_ref'])
        run.assert_not_called()


def test_remote_replay_disagreement_cannot_become_workflow_completed_negative(tmp_path):
    operation = catalog.REGISTRY['mechanism.plan_scan']
    def inconsistent_kernel(**inputs):
        result = operation.kernel(**inputs)
        result['trials'][0]['outcome'] = 'TARGET_MATCH'
        result['matches'] = [{**result['trials'][0], 'candidate_hex': '41'}]
        return result
    def runner(operation_id, inputs):
        if operation_id == 'mechanism.plan_inspect':
            return catalog.run(operation_id, inputs)
        with patch.dict(catalog.REGISTRY, {operation_id: replace(operation, kernel=inconsistent_kernel)}):
            return catalog.run(operation_id, inputs)
    with Continuation(tmp_path) as workflow:
        ticket = prepare(workflow)
        remote = workflow.run_remote_page(ticket['ticket_ref'], runner)
        assert workflow.replay_remote_page(remote['event_id'])['status'] == 'MISMATCH'
        report = workflow.handoff(ticket['ticket_ref'])
        assert report['local_coverage']['complete']  # Preserve actual internally recorded work.
        assert not report['completed_negative'] and report['conclusion'] == 'INCONCLUSIVE'


def test_failed_or_unrun_declared_calibration_blocks_workflow_negative(tmp_path):
    case, plan, bindings = fixture()
    case['calibrations'] = [{'id': 'bad-control', 'operation_id': 'text.encode',
        'inputs': {'codec': 'ascii'}, 'artifact_bindings': {'text': 'evidence'},
        'output_field': 'hex', 'expected_value_sha256': 'a' * 64, 'source': 'deliberately wrong control'}]
    with Continuation(tmp_path) as workflow:
        ticket = workflow.prepare(case, plan, bindings)
        workflow.run_page(ticket['ticket_ref'])
        before = workflow.handoff(ticket['ticket_ref'])
        assert before['local_coverage']['complete'] and before['calibration_state'] == 'NOT_RUN'
        assert not before['completed_negative']
        workflow.replay_controls(ticket['ticket_ref'])
        after = workflow.handoff(ticket['ticket_ref'])
        assert after['calibration_state'] == 'CALIBRATION_FAILED'
        assert not after['completed_negative'] and after['conclusion'] == 'INCONCLUSIVE'


def test_later_passing_control_does_not_erase_unretracted_failed_report(tmp_path):
    case, plan, bindings = fixture()
    case['calibrations'] = [{'id': 'control', 'operation_id': 'text.encode',
        'inputs': {'codec': 'ascii'}, 'artifact_bindings': {'text': 'evidence'},
        'output_field': 'hex', 'expected_value_sha256': hashlib.sha256(encoded(b'01000001'.hex())).hexdigest(),
        'source': 'synthetic known control'}]
    operation = catalog.REGISTRY['text.encode']
    def wrong_control(**inputs):
        result = operation.kernel(**inputs)
        result['hex'] = '00'
        return result
    with Continuation(tmp_path) as workflow:
        ticket = workflow.prepare(case, plan, bindings)
        with patch.dict(catalog.REGISTRY, {'text.encode': replace(operation, kernel=wrong_control)}):
            first = workflow.replay_controls(ticket['ticket_ref'])
        assert first['status'] == 'CALIBRATION_FAILED'
        assert workflow.replay_controls(ticket['ticket_ref'])['status'] == 'CALIBRATED'
        workflow.run_page(ticket['ticket_ref'])
        report = workflow.handoff(ticket['ticket_ref'])
        assert report['calibration_state'] == 'CALIBRATED'  # Latest state is retained, not a conflict eraser.
        assert report['unresolved_control_reports'] == [first['review_event_id']]
        assert not report['completed_negative'] and report['conclusion'] == 'INCONCLUSIVE'
        workflow.ledger.append('retraction', {'reason': 'synthetic faulty calibration withdrawn'},
                               retracts=first['review_event_id'])
        report = workflow.handoff(ticket['ticket_ref'])
        assert not report['unresolved_control_reports'] and report['completed_negative']


def test_retracting_control_execution_invalidates_its_dependent_report(tmp_path):
    case, plan, bindings = fixture()
    case['calibrations'] = [{'id': 'control', 'operation_id': 'text.encode',
        'inputs': {'codec': 'ascii'}, 'artifact_bindings': {'text': 'evidence'},
        'output_field': 'hex', 'expected_value_sha256': hashlib.sha256(encoded(b'01000001'.hex())).hexdigest(),
        'source': 'synthetic known control'}]
    with Continuation(tmp_path) as workflow:
        ticket = workflow.prepare(case, plan, bindings)
        control = workflow.replay_controls(ticket['ticket_ref'])
        workflow.run_page(ticket['ticket_ref'])
        assert workflow.handoff(ticket['ticket_ref'])['completed_negative']
        workflow.ledger.append('retraction', {'reason': 'control execution withdrawn'},
                               retracts=control['execution_event_ids'][0])
        report = workflow.handoff(ticket['ticket_ref'])
        assert report['calibrations'][0]['review_status'] == 'REVIEW_REQUIRED'
        assert report['calibration_state'] == 'NOT_RUN' and not report['completed_negative']


@pytest.mark.parametrize('claim_status', ['CALIBRATED', 'NO_CALIBRATIONS', 'CALIBRATION_FAILED'])
def test_generic_control_report_cannot_promote_not_run_even_with_real_unrelated_execution(tmp_path, claim_status):
    with Continuation(tmp_path) as workflow:
        ticket = workflow.prepare(*control_fixture())
        workflow.run_page(ticket['ticket_ref'])
        unrelated = workflow.ledger.run('text.encode', {'text': 'unrelated', 'codec': 'ascii'},
                                       dependencies=[ticket['event_id']])
        report = {'status': claim_status, 'complete': True, 'execution_origin': 'local',
                  'controls': [], 'independent_reproduction': False}
        report_ref = workflow.workspace.put(encoded(report))
        fake = workflow.ledger.append('review', {'continuation_schema': 1, 'mode': 'controls',
            'calibration_schema': 1, 'ticket_ref': ticket['ticket_ref'], 'report_ref': report_ref,
            'execution_event_ids': [unrelated['ledger_event_id']]},
            dependencies=[ticket['event_id'], unrelated['ledger_event_id']])
        handoff = workflow.handoff(ticket['ticket_ref'])
        assert handoff['calibration_state'] == 'NOT_RUN' and not handoff['completed_negative']
        claim, = handoff['calibrations']
        assert claim['event_id'] == fake and not claim['internally_indexed']
        assert not claim['qualifying_local_record'] and claim['report']['status'] == claim_status
        workflow.replay_controls(ticket['ticket_ref'])
        assert workflow.handoff(ticket['ticket_ref'])['completed_negative']


def test_copy_of_retracted_genuine_report_is_still_only_a_claim(tmp_path):
    with Continuation(tmp_path) as workflow:
        ticket = workflow.prepare(*control_fixture())
        genuine = workflow.replay_controls(ticket['ticket_ref'])
        workflow.run_page(ticket['ticket_ref'])
        original = workflow.ledger.calibration_reviews()[genuine['review_event_id']]
        workflow.ledger.append('retraction', {'reason': 'synthetic review withdrawal'},
                               retracts=genuine['review_event_id'])
        copied = workflow.ledger.append('review', deepcopy(original['payload']),
                                        dependencies=original['dependencies'])
        handoff = workflow.handoff(ticket['ticket_ref'])
        assert not handoff['completed_negative'] and handoff['calibration_state'] == 'NOT_RUN'
        copy = next(row for row in handoff['calibrations'] if row['event_id'] == copied)
        assert not copy['internally_indexed'] and not copy['qualifying_local_record']


def test_internal_calibration_recorder_rejects_unrelated_request_and_wrong_control_rows(tmp_path):
    case, plan, bindings = control_fixture()
    with Continuation(tmp_path) as workflow:
        ticket = workflow.prepare(case, plan, bindings)
        packet = json.loads(workflow.workspace.get(ticket['ticket_ref']))
        unrelated = workflow.ledger.run('text.encode', {'text': 'unrelated', 'codec': 'ascii'},
                                       dependencies=[ticket['event_id']])
        report_ref = workflow.workspace.put(encoded({'status': 'CALIBRATED'}))
        record = {name: case['calibrations'][0][name] for name in
                  ('id', 'operation_id', 'output_field', 'expected_value_sha256')}
        record.update(status='REPLAY_MATCH', inputs={'text': '01000001', 'codec': 'ascii'}, envelope=unrelated)
        kwargs = {'ticket_ref': ticket['ticket_ref'], 'manifest_sha256': packet['manifest_sha256'],
                  'controls_sha256': hashlib.sha256(encoded(packet['case']['calibrations'])).hexdigest(),
                  'report_ref': report_ref, 'preparation_id': ticket['event_id'],
                  'declared_controls': packet['case']['calibrations']}
        with pytest.raises(ValueError, match='executed request/result'):
            workflow.ledger._record_calibration_review(**kwargs, records=[record])
        record['id'] = 'wrong-control'
        with pytest.raises(ValueError, match='declared control order'):
            workflow.ledger._record_calibration_review(**kwargs, records=[record])
        assert workflow.ledger.calibration_reviews() == {}


def test_calibration_index_hash_mismatch_fails_closed(tmp_path):
    with Continuation(tmp_path) as workflow:
        ticket = workflow.prepare(*control_fixture())
        report = workflow.replay_controls(ticket['ticket_ref'])
        workflow.ledger.connection.execute('UPDATE calibration_reviews SET payload_sha256=? WHERE event_id=?',
                                           ('a' * 64, report['review_event_id']))
        workflow.ledger.connection.commit()
        with pytest.raises(ValueError, match='calibration review integrity'):
            workflow.handoff(ticket['ticket_ref'])


def test_report_cannot_omit_or_change_internally_recorded_control_rows(tmp_path):
    with Continuation(tmp_path) as workflow:
        ticket = workflow.prepare(*control_fixture())
        report = workflow.replay_controls(ticket['ticket_ref'])
        packet = json.loads(workflow.workspace.get(ticket['ticket_ref']))
        indexed = workflow.ledger.calibration_reviews()[report['review_event_id']]
        stored = json.loads(workflow.workspace.get(indexed['payload']['report_ref']))
        missing = {**stored, 'controls': []}
        with pytest.raises(ValueError, match='ticket controls'):
            workflow._qualifying_controls(packet, indexed, missing)
        changed = deepcopy(stored)
        changed['controls'][0]['observed_value_sha256'] = 'a' * 64
        with pytest.raises(ValueError, match='observed hash/status'):
            workflow._qualifying_controls(packet, indexed, changed)


def test_calibration_review_and_internal_index_commit_atomically(tmp_path):
    with Continuation(tmp_path) as workflow:
        ticket = workflow.prepare(*control_fixture())
        workflow.ledger.connection.execute("CREATE TRIGGER stop_calibration_index BEFORE INSERT ON calibration_reviews BEGIN SELECT RAISE(ABORT,'synthetic calibration index failure'); END")
        workflow.ledger.connection.commit()
        import sqlite3
        with pytest.raises(sqlite3.IntegrityError, match='synthetic calibration index failure'):
            workflow.replay_controls(ticket['ticket_ref'])
        assert workflow.ledger.calibration_reviews() == {}
        handoff = workflow.handoff(ticket['ticket_ref'])
        assert handoff['calibration_state'] == 'NOT_RUN' and handoff['calibrations'] == []


def test_missing_source_after_genuine_calibration_remains_inconclusive(tmp_path):
    case, plan, bindings = control_fixture()
    with Continuation(tmp_path) as workflow:
        ticket = workflow.prepare(case, plan, bindings)
        assert workflow.replay_controls(ticket['ticket_ref'])['status'] == 'CALIBRATED'
        workflow.run_page(ticket['ticket_ref'])
        assert workflow.handoff(ticket['ticket_ref'])['completed_negative']
        workflow.workspace.connection.execute('DELETE FROM artifacts WHERE sha=?',
                                              (case['artifacts'][0]['sha256'],))
        workflow.workspace.connection.commit()
        handoff = workflow.handoff(ticket['ticket_ref'])
        assert handoff['local_coverage']['complete']
        assert not handoff['inspection']['ready'] and not handoff['inspection']['bound_sources_ready']
        assert handoff['calibration_state'] == 'NOT_RUN'
        assert handoff['conclusion'] == 'INCONCLUSIVE' and not handoff['completed_negative']


@pytest.mark.parametrize('mutation', ['inputs', 'result', 'fingerprint', 'version'])
def test_remote_response_mutation_cannot_bind_to_another_request(tmp_path, mutation):
    def runner(operation_id, inputs):
        if operation_id == 'mechanism.plan_inspect':
            return catalog.run(operation_id, inputs)
        if mutation == 'inputs':
            inputs['plan']['sources'][0]['value'] = '01000010'
            inputs['expected_plan_id'] = None
            return catalog.run(operation_id, inputs)
        result = catalog.run(operation_id, inputs)
        if mutation == 'result':
            result['result']['coverage']['completed'] += 1
        elif mutation == 'fingerprint':
            result['receipt']['preparation_implementation_fingerprint'] = 'a' * 64
        else:
            result['receipt']['operation_version'] = '999'
        return result
    with Continuation(tmp_path) as workflow:
        ticket = prepare(workflow)
        with pytest.raises(ValueError):
            workflow.run_remote_page(ticket['ticket_ref'], runner)
        assert workflow.handoff(ticket['ticket_ref'])['remote_pages'] == []


def test_coherent_remote_platform_fingerprint_can_differ_from_client(tmp_path):
    def runner(operation_id, inputs):
        with patch.object(catalog, 'implementation_fingerprint', return_value='a' * 64):
            return catalog.run(operation_id, inputs)
    with Continuation(tmp_path) as workflow:
        ticket = prepare(workflow)
        remote = workflow.run_remote_page(ticket['ticket_ref'], runner)
        assert remote['envelope']['receipt']['implementation_fingerprint'] == 'a' * 64
        assert remote['state'] == 'REPLAY_REQUIRED'
        assert workflow.replay_remote_page(remote['event_id'])['status'] == 'MATCH'


def test_remote_final_implementation_change_is_rejected(tmp_path):
    fingerprint = {'value': 'a' * 64}
    operation = catalog.REGISTRY['mechanism.plan_scan']
    def changing_kernel(**inputs):
        result = operation.kernel(**inputs)
        fingerprint['value'] = 'b' * 64
        return result
    def runner(operation_id, inputs):
        with patch.object(catalog, 'implementation_fingerprint', side_effect=lambda: fingerprint['value']):
            if operation_id == 'mechanism.plan_inspect':
                return catalog.run(operation_id, inputs)
            with patch.dict(catalog.REGISTRY, {operation_id: replace(operation, kernel=changing_kernel)}):
                return catalog.run(operation_id, inputs)
    with Continuation(tmp_path) as workflow:
        ticket = prepare(workflow)
        with pytest.raises(ValueError):
            workflow.run_remote_page(ticket['ticket_ref'], runner)
        assert workflow.handoff(ticket['ticket_ref'])['remote_pages'] == []


def test_remote_retraction_also_invalidates_local_replay(tmp_path):
    with Continuation(tmp_path) as workflow:
        ticket = prepare(workflow)
        remote = workflow.run_remote_page(ticket['ticket_ref'], catalog.run)
        workflow.replay_remote_page(remote['event_id'])
        workflow.ledger.append('retraction', {'reason': 'remote input needs review'}, retracts=remote['event_id'])
        result = workflow.handoff(ticket['ticket_ref'])
        assert not result['local_coverage']['complete']
        assert result['remote_pages'][0]['review_status'] == 'RETRACTED'
        assert result['local_replays'][0]['review_status'] == 'REVIEW_REQUIRED'


def test_portable_packet_restores_evidence_but_never_fabricates_previous_coverage(tmp_path):
    with Continuation(tmp_path / 'first') as workflow:
        ticket = prepare(workflow)
        workflow.run_page(ticket['ticket_ref'])
        portable = json.loads(json.dumps(workflow.export_packet(ticket['ticket_ref'])))
    with Continuation(tmp_path / 'second') as workflow:
        restored = workflow.restore_packet(portable)
        assert restored['inspection']['ready'] and restored['history'] == 'NOT_IMPORTED'
        assert workflow.handoff(ticket['ticket_ref'])['local_coverage']['counts']['attempted'] == 0
        assert workflow.run_page(ticket['ticket_ref'])['result']['complete']


def test_missing_portable_evidence_remains_missing_and_mutation_is_rejected(tmp_path):
    with Continuation(tmp_path / 'first') as workflow:
        ticket = prepare(workflow)
        portable = workflow.export_packet(ticket['ticket_ref'])
    artifact = next(row for row in portable['artifacts'] if row['handle'] != ticket['ticket_ref'])
    corrupted = deepcopy(portable)
    next(row for row in corrupted['artifacts'] if row['handle'] == artifact['handle'])['base64'] = base64.b64encode(b'bad').decode()
    with Continuation(tmp_path / 'bad') as workflow, pytest.raises(ValueError, match='content/hash'):
        workflow.restore_packet(corrupted)
    artifact.update(status='MISSING', base64=None)
    with Continuation(tmp_path / 'missing') as workflow:
        restored = workflow.restore_packet(portable)
        assert not restored['inspection']['ready']
        with pytest.raises(ValueError, match='missing or corrupt'):
            workflow.run_page(ticket['ticket_ref'])


@pytest.mark.parametrize('mutation', ['missing_bindings', 'wrong_missing_artifact'])
def test_coherently_rehashed_portable_ticket_cannot_reuse_coverage_with_invalid_bindings(tmp_path, mutation):
    from polya.casepacks import inspect_case
    with Continuation(tmp_path) as workflow:
        ticket = prepare(workflow)
        workflow.run_page(ticket['ticket_ref'])
        assert workflow.handoff(ticket['ticket_ref'])['completed_negative']
        portable = workflow.export_packet(ticket['ticket_ref'])
        ticket_artifact = next(row for row in portable['artifacts'] if row['handle'] == ticket['ticket_ref'])
        packet = json.loads(base64.b64decode(ticket_artifact['base64']))
        old_sha = packet['case']['artifacts'][0]['sha256']
        packet['case']['artifacts'][0].update(sha256='a' * 64, required=False)
        packet['manifest_sha256'] = inspect_case(packet['case'])['manifest_sha256']
        if mutation == 'missing_bindings':
            packet['source_bindings'] = {}
        raw = encoded(packet)
        changed_ref = 'sha256:' + hashlib.sha256(raw).hexdigest()
        portable['ticket_ref'] = changed_ref
        ticket_artifact.update(handle=changed_ref, base64=base64.b64encode(raw).decode())
        next(row for row in portable['artifacts'] if row['handle'] == 'sha256:' + old_sha).update(
            handle='sha256:' + 'a' * 64, status='MISSING', base64=None)
        with pytest.raises(ValueError, match='bind every plan source|actual plan source bytes'):
            workflow.restore_packet(portable)
        with pytest.raises(ValueError, match='bind every plan source|actual plan source bytes'):
            workflow.handoff(changed_ref)
        assert workflow.handoff(ticket['ticket_ref'])['completed_negative']
