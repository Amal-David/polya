"""Client-owned continuation using existing case packs, Workspace and Ledger.

No paths, persistence or network callbacks are exposed through the MCP registry.
Remote callbacks are trusted host code. Their receipts remain recorded claims
until a local Ledger execution replays the request; hashes are not authentication.
"""
from __future__ import annotations

import base64
from copy import deepcopy
import hashlib
from pathlib import Path
import time
from typing import Callable

from . import catalog
from .casepacks import CasePack, encoded, inspect_case
from .jsonio import loads
from .ledger import Ledger, _page_summary, _validate_receipt
from .plans import ScanInput, prepare_plan
from .workspace import Workspace

PLAN_OPERATION = 'mechanism.plan_scan'
MAX_TRANSFER = 2_000_000
Runner = Callable[[str, dict], dict]


def _sha(value) -> str:
    return hashlib.sha256(encoded(value)).hexdigest()


def _plan_id(plan: dict, fingerprint: str) -> str:
    return _sha({'schema': 1, 'implementation': fingerprint, 'plan': plan})


def _source_bytes(source: dict) -> bytes:
    if source['kind'] == 'png':
        return base64.b64decode(source['value'], validate=True)
    if source['kind'] == 'bytes':
        return bytes.fromhex(source['value'])
    return source['value'].encode('utf-8')


def _remote_receipt(operation_id: str, inputs: dict, envelope: dict,
                    fingerprint: str | None = None) -> dict:
    """Check exact normalized request/result binding, without importing coverage."""
    op = catalog.REGISTRY[operation_id]
    normalized = op.request.model_validate(inputs).model_dump(mode='json')
    if type(envelope) is not dict:
        raise ValueError('remote runner must return an operation envelope object')
    receipt = envelope.get('receipt', {})
    if type(receipt) is not dict:
        raise ValueError('remote receipt must be an object')
    observed = receipt.get('preparation_implementation_fingerprint')
    if fingerprint is not None and observed != fingerprint:
        raise ValueError('remote implementation changed after inspection; inspect again')
    before = receipt.get('runtime_observations', {}).get('before')
    identity = {'operation_id': operation_id, 'operation_version': op.version,
                'implementation': observed, 'inputs': normalized, 'runtime_mode': before}
    key = _sha(identity)
    verified = _validate_receipt(operation_id, normalized, envelope, identity, key,
                                 expected_implementation=observed)
    if verified['runtime_observations']['changed'] or verified.get('implementation_changed'):
        raise ValueError('remote runtime changed during execution; inspect again')
    return verified


class Continuation:
    """A trusted Python client owns this directory and each instance's lifetime.

    This is a workflow adapter over existing storage, not a server-side session.
    One Workspace instance must not be shared between worker threads.
    """

    def __init__(self, directory: str | Path):
        self.workspace = Workspace(directory)
        self.ledger = Ledger(self.workspace.root / 'history.sqlite')

    def prepare(self, case: dict, plan: dict, source_bindings: dict[str, str]) -> dict:
        """Freeze inspected source bytes, conventions, plan and implementation.

        Every plan source must bind to one case artifact. Available inline bytes
        are moved to existing content handles; caller-owned dictionaries are copied.
        """
        frozen_case = CasePack.model_validate(deepcopy(case)).model_dump(mode='json')
        inspection = inspect_case(frozen_case, artifact_loader=self.workspace.get)
        if not inspection['ready']:
            raise ValueError('required case evidence is missing or corrupt')
        for artifact in frozen_case['artifacts']:
            content = artifact['content']
            if content is not None:
                raw = bytes.fromhex(content) if artifact['encoding'] == 'hex' else content.encode('utf-8')
                self.workspace.put(raw)
                artifact['content'] = None
        hydrated = self.workspace.hydrate_plan(deepcopy(plan))
        self._check_sources(frozen_case, hydrated, source_bindings)
        _, plan_id, total, _ = prepare_plan(hydrated)
        packet = {'schema': 1, 'case': frozen_case, 'plan': hydrated,
                  'source_bindings': deepcopy(source_bindings),
                  'manifest_sha256': inspection['manifest_sha256'], 'plan_id': plan_id,
                  'implementation_fingerprint': catalog.implementation_fingerprint(),
                  'operation_id': PLAN_OPERATION,
                  'operation_version': catalog.REGISTRY[PLAN_OPERATION].version,
                  'generated_ordinals': total}
        ref = self.workspace.put(encoded(packet))
        event_id = self.ledger.append('observation', {'continuation_schema': 1,
            'mode': 'prepared', 'ticket_ref': ref})
        return {'ticket_ref': ref, 'event_id': event_id, 'plan_id': plan_id,
                'inspection': inspect_case(frozen_case, artifact_loader=self.workspace.get),
                'generated_ordinals': total, 'unique_candidates': None}

    def _check_sources(self, case: dict, plan: dict, bindings: dict[str, str], *,
                       require_available: bool = True) -> bool:
        if (type(bindings) is not dict or
                set(bindings) != {source['id'] for source in plan['sources']} or
                any(type(value) is not str for value in bindings.values())):
            raise ValueError('bind every plan source to one case artifact ID')
        artifacts = {artifact['id']: artifact for artifact in case['artifacts']}
        available = True
        for source in plan['sources']:
            artifact = artifacts.get(bindings[source['id']])
            if artifact is None:
                raise ValueError('source binding names an unknown case artifact')
            expected_encoding = 'hex' if source['kind'] in ('bytes', 'png') else 'utf8'
            raw = _source_bytes(source)
            if (artifact['encoding'] != expected_encoding or
                    hashlib.sha256(raw).hexdigest() != artifact['sha256']):
                raise ValueError('actual plan source bytes do not match inspected case artifact')
            try:
                stored = self.workspace.get('sha256:' + artifact['sha256'])
            except KeyError as exc:
                if require_available:
                    raise ValueError('bound plan source artifact is missing') from exc
                available = False
                continue
            if stored != raw:
                raise ValueError('actual plan source bytes do not match inspected case artifact')
        return available

    def _load(self, ticket_ref: str, *, require_ready: bool = True) -> tuple[dict, dict, bool]:
        packet = loads(self.workspace.get(ticket_ref))
        expected = {'schema', 'case', 'plan', 'source_bindings', 'manifest_sha256', 'plan_id',
                    'implementation_fingerprint', 'operation_id', 'operation_version', 'generated_ordinals'}
        if (type(packet) is not dict or set(packet) != expected or packet['schema'] != 1 or
                packet['operation_id'] != PLAN_OPERATION or
                packet['plan_id'] != _plan_id(packet['plan'], packet['implementation_fingerprint'])):
            raise ValueError('invalid continuation packet')
        _, _, total, _ = prepare_plan(packet['plan'])
        if (type(packet['generated_ordinals']) is not int or
                packet['generated_ordinals'] != total):
            raise ValueError('declared recipe count changed')
        inspection = inspect_case(packet['case'], artifact_loader=self.workspace.get)
        inspection['bound_sources_ready'] = self._check_sources(
            packet['case'], packet['plan'], packet['source_bindings'], require_available=False)
        if inspection['manifest_sha256'] != packet['manifest_sha256']:
            raise ValueError('case manifest changed after inspection')
        compatible = (packet['implementation_fingerprint'] == catalog.implementation_fingerprint() and
                      packet['operation_version'] == catalog.REGISTRY[PLAN_OPERATION].version)
        if require_ready:
            if not compatible:
                raise ValueError('implementation or operation version changed; prepare a new ticket')
            if not inspection['ready']:
                raise ValueError('required case evidence is missing or corrupt')
            self._check_sources(packet['case'], packet['plan'], packet['source_bindings'])
        return packet, inspection, compatible

    def _preparation(self, ticket_ref: str) -> str:
        matches = [event for event in self.ledger.snapshot()['events']
                   if event['kind'] == 'observation' and event['payload'].get('mode') == 'prepared'
                   and event['payload'].get('ticket_ref') == ticket_ref]
        if not matches or matches[-1]['review_status'] != 'RECORDED':
            raise ValueError('preparation evidence is absent, retracted or requires review')
        return matches[-1]['id']

    def request(self, ticket_ref: str, *, start: int | None = None, **limits) -> dict:
        """Return detached exact local inputs; budgets cannot replace the bound plan."""
        if set(limits) - {'max_trials', 'max_matches', 'max_work', 'timeout_ms'}:
            raise ValueError('only declared page budgets may be overridden')
        packet, _, _ = self._load(ticket_ref)
        self._preparation(ticket_ref)
        if start is None:
            coverage = self.ledger.plan_coverage(packet['plan_id'])
            unresolved = coverage['unresolved_ranges']
            start = unresolved[0][0] if unresolved else 0 if not coverage['known'] else packet['generated_ordinals']
        return ScanInput(plan=packet['plan'], start=start,
                         expected_plan_id=packet['plan_id'], **limits).model_dump(mode='json')

    def run_page(self, ticket_ref: str, *, start: int | None = None,
                 dependencies: list[str] | None = None, **limits) -> dict:
        """Execute the bound request through Ledger.run; interruption commits no page."""
        inputs = self.request(ticket_ref, start=start, **limits)
        deps = [self._preparation(ticket_ref), *(dependencies or [])]
        return self.ledger.run(PLAN_OPERATION, inputs, dependencies=list(dict.fromkeys(deps)))

    def run_remote_page(self, ticket_ref: str, runner: Runner, *, start: int = 0, **limits) -> dict:
        """Inspect and run exact inline sources through a host's stateless MCP adapter.

        The callback accepts an operation ID and input dict and returns the ordinary
        envelope from ``puzzle.run``. No network or credentials are supplied here.
        Remote pages are generic claims in Ledger, never execution coverage.
        """
        inputs = self.request(ticket_ref, start=start, **limits)
        inspection_inputs = {'plan': deepcopy(inputs['plan'])}
        inspection = runner('mechanism.plan_inspect', deepcopy(inspection_inputs))
        receipt = _remote_receipt('mechanism.plan_inspect', inspection_inputs, inspection)
        fingerprint = receipt['implementation_fingerprint']
        expected_id = _plan_id(inputs['plan'], fingerprint)
        if not inspection['result']['valid'] or inspection['result']['plan_id'] != expected_id:
            raise ValueError('remote plan inspection did not bind the supplied plan')
        inputs['expected_plan_id'] = expected_id
        frozen_inputs = loads(encoded(inputs))
        envelope = runner(PLAN_OPERATION, deepcopy(frozen_inputs))
        verified = _remote_receipt(PLAN_OPERATION, frozen_inputs, envelope, fingerprint)
        page = _page_summary(frozen_inputs, envelope['result'], verified)
        request_ref = self.workspace.put(encoded(frozen_inputs))
        response_ref = self.workspace.put(encoded(envelope))
        event_id = self.ledger.append('experiment', {'continuation_schema': 1,
            'mode': 'remote', 'ticket_ref': ticket_ref, 'request_ref': request_ref,
            'response_ref': response_ref, 'page': page}, dependencies=[self._preparation(ticket_ref)])
        return {'event_id': event_id, 'envelope': envelope, 'state': 'REPLAY_REQUIRED',
                'locally_recorded_execution': False, 'certified_negative': False}

    def replay_controls(self, ticket_ref: str, *, runner: Runner | None = None,
                        timeout_ms: int = 5000) -> dict:
        """Resolve stored artifacts into the actual allowlisted control requests.

        This retains the existing CasePack calibration semantics and admission
        rules without inflating handles into its smaller inline-content fields.
        A remote control is still a caller-reported receipt, not local execution.
        """
        if type(timeout_ms) is not int or not 1 <= timeout_ms <= 60000:
            raise ValueError('timeout_ms must be an integer in [1,60000]')
        packet, _, _ = self._load(ticket_ref)
        preparation = self._preparation(ticket_ref)
        artifacts = {artifact['id']: artifact for artifact in packet['case']['artifacts']}
        deadline = time.monotonic() + timeout_ms / 1000
        rows = []
        execution_events = []
        records = []
        interrupted = False
        for control in packet['case']['calibrations']:
            if time.monotonic() >= deadline:
                interrupted = True
                break
            inputs = deepcopy(control['inputs'])
            for field, artifact_id in control['artifact_bindings'].items():
                artifact = artifacts[artifact_id]
                raw = self.workspace.get('sha256:' + artifact['sha256'])
                inputs[field] = raw.hex() if artifact['encoding'] == 'hex' else raw.decode('utf-8')
            operation_id = catalog.canonical_operation_id(control['operation_id'])
            record = {name: control[name] for name in ('id', 'output_field', 'expected_value_sha256')}
            record.update(operation_id=operation_id, inputs=deepcopy(inputs), envelope=None)
            try:
                if runner is None:
                    envelope = self.ledger.run(operation_id, inputs, dependencies=[preparation])
                    execution_events.append(envelope['ledger_event_id'])
                else:
                    envelope = runner(operation_id, deepcopy(inputs))
                    _remote_receipt(operation_id, inputs, envelope)
                observed = _sha(envelope['result'][control['output_field']])
            except (ValueError, RuntimeError, ImportError, KeyError) as exc:
                rows.append({'id': control['id'], 'status': 'EXECUTION_ERROR',
                             'error_type': type(exc).__name__})
                records.append({**record, 'status': 'EXECUTION_ERROR'})
                continue
            if time.monotonic() >= deadline:
                interrupted = True
                rows.append({'id': control['id'], 'status': 'LATE_RESULT',
                             'receipt': envelope['receipt']})
                records.append({**record, 'status': 'LATE_RESULT', 'envelope': deepcopy(envelope)})
                break
            control_status = 'REPLAY_MATCH' if observed == control['expected_value_sha256'] else 'REPLAY_MISMATCH'
            rows.append({'id': control['id'], 'status': control_status,
                         'observed_value_sha256': observed, 'receipt': envelope['receipt']})
            records.append({**record, 'status': control_status, 'envelope': deepcopy(envelope)})
        complete = not interrupted and len(rows) == len(packet['case']['calibrations'])
        status = ('PARTIAL' if not complete else 'NO_CALIBRATIONS' if not rows else
                  'CALIBRATED' if all(row['status'] == 'REPLAY_MATCH' for row in rows) else 'CALIBRATION_FAILED')
        report = {'status': status, 'complete': complete, 'controls': rows,
                  'execution_origin': 'local' if runner is None else 'remote_claim',
                  'independent_reproduction': False,
                  'scope': 'Known caller-declared controls only; a match does not verify the interpretation or an unknown result. Callback and operation deadlines are cooperative.'}
        report_ref = self.workspace.put(encoded(report))
        if runner is None:
            review_id = self.ledger._record_calibration_review(
                ticket_ref=ticket_ref, manifest_sha256=packet['manifest_sha256'],
                controls_sha256=_sha(packet['case']['calibrations']), report_ref=report_ref,
                preparation_id=preparation, declared_controls=packet['case']['calibrations'], records=records)
        else:
            review_id = self.ledger.append('review', {'continuation_schema': 1, 'mode': 'controls',
                'ticket_ref': ticket_ref, 'report_ref': report_ref}, dependencies=[preparation])
        return {**report, 'review_event_id': review_id, 'execution_event_ids': execution_events}

    def _qualifying_controls(self, packet: dict, indexed: dict, report: dict) -> bool:
        """Match an internally indexed report to this ticket's exact control inputs."""
        payload = indexed['payload']
        declared = packet['case']['calibrations']
        if (payload['manifest_sha256'] != packet['manifest_sha256'] or
                payload['controls_sha256'] != _sha(declared) or
                payload['control_count'] != len(declared) or
                report.get('execution_origin') != 'local' or
                type(report.get('complete')) is not bool or
                type(report.get('controls')) is not list or
                len(report['controls']) != len(payload['records'])):
            raise ValueError('indexed calibration report does not match the ticket controls')
        complete = report['complete']
        if complete and len(payload['records']) != len(declared):
            raise ValueError('complete calibration does not cover every declared control')
        artifacts = {artifact['id']: artifact for artifact in packet['case']['artifacts']}
        for control, row, recorded in zip(declared, report['controls'], payload['records']):
            operation_id = catalog.canonical_operation_id(control['operation_id'])
            if (any(recorded[key] != control[key] for key in ('id', 'output_field', 'expected_value_sha256')) or
                    recorded['operation_id'] != operation_id or row.get('id') != control['id'] or
                    row.get('status') != recorded['status']):
                raise ValueError('indexed calibration row does not match its declared control')
            if recorded['execution_event_id'] is None:
                if recorded['status'] != 'EXECUTION_ERROR' or 'receipt' in row:
                    raise ValueError('calibration error row must not claim an execution receipt')
                continue
            inputs = deepcopy(control['inputs'])
            for field, artifact_id in control['artifact_bindings'].items():
                artifact = artifacts[artifact_id]
                try:
                    raw = self.workspace.get('sha256:' + artifact['sha256'])
                except KeyError:
                    return False
                inputs[field] = raw.hex() if artifact['encoding'] == 'hex' else raw.decode('utf-8')
            operation = catalog.REGISTRY[operation_id]
            normalized = operation.request.model_validate(inputs).model_dump(mode='json')
            receipt = row.get('receipt')
            if (recorded['inputs_sha256'] != _sha(normalized) or type(receipt) is not dict or
                    _sha(receipt) != recorded['receipt_sha256'] or
                    receipt.get('result_sha256') != recorded['result_sha256'] or
                    receipt.get('operation_version') != recorded['operation_version']):
                raise ValueError('calibration request/output receipt does not match actual execution')
            expected_status = ('REPLAY_MATCH' if recorded['observed_value_sha256'] ==
                               recorded['expected_value_sha256'] else 'REPLAY_MISMATCH')
            if recorded['status'] == 'LATE_RESULT':
                if complete:
                    raise ValueError('late calibration result cannot be complete')
            elif (recorded['status'] != expected_status or
                  row.get('observed_value_sha256') != recorded['observed_value_sha256']):
                raise ValueError('calibration observed hash/status linkage mismatch')
        expected = ('PARTIAL' if not complete else 'NO_CALIBRATIONS' if not declared else
                    'CALIBRATED' if all(row['status'] == 'REPLAY_MATCH' for row in payload['records'])
                    else 'CALIBRATION_FAILED')
        if report.get('status') != expected:
            raise ValueError('indexed calibration aggregate status is inconsistent')
        return True

    def _remote_event(self, event_id: str) -> tuple[dict, dict, dict]:
        event = next((event for event in self.ledger.snapshot()['events'] if event['id'] == event_id), None)
        if (event is None or event['payload'].get('mode') != 'remote' or
                event['payload'].get('continuation_schema') != 1):
            raise ValueError('expected a recorded remote continuation event')
        payload = event['payload']
        inputs = loads(self.workspace.get(payload['request_ref']))
        envelope = loads(self.workspace.get(payload['response_ref']))
        receipt = _remote_receipt(PLAN_OPERATION, inputs, envelope)
        if _page_summary(inputs, envelope['result'], receipt) != payload['page']:
            raise ValueError('remote page summary changed')
        packet, _, _ = self._load(payload['ticket_ref'], require_ready=False)
        if inputs['plan'] != packet['plan']:
            raise ValueError('remote response is not bound to this ticket plan')
        return event, inputs, envelope

    def replay_remote_page(self, event_id: str) -> dict:
        """Run internally, preserving a separate replay state and implementation limit."""
        event, inputs, remote = self._remote_event(event_id)
        if event['review_status'] != 'RECORDED':
            raise ValueError('remote evidence is retracted or requires review')
        limits = {name: inputs[name] for name in ('max_trials', 'max_matches', 'max_work', 'timeout_ms')}
        local = self.run_page(event['payload']['ticket_ref'], start=inputs['start'],
                              dependencies=[event_id], **limits)
        def terminal(result):
            return [{key: row.get(key) for key in ('ordinal', 'choices', 'outcome', 'candidate_sha256')}
                    for row in result['trials']]
        left, right = terminal(local['result']), terminal(remote['result'])
        common = min(len(left), len(right))
        status = ('MISMATCH' if left[:common] != right[:common] else
                  'MATCH' if len(left) == len(right) else 'PARTIAL')
        review_id = self.ledger.append('review', {'continuation_schema': 1, 'mode': 'replay',
            'remote_event_id': event_id, 'local_event_id': local['ledger_event_id'], 'status': status,
            'implementation_independent': False}, dependencies=[event_id, local['ledger_event_id']])
        return {'status': status, 'envelope': local, 'review_event_id': review_id,
                'independent_reproduction': False,
                'scope': 'Same-code local replay compares terminal ordinals/outcomes/hashes; it is not implementation-independent validation.'}

    def handoff(self, ticket_ref: str) -> dict:
        """Read actual local coverage and retain remote claims, gaps and retractions."""
        owned_transaction = not self.ledger.connection.in_transaction
        try:
            if owned_transaction:
                self.ledger.connection.execute('BEGIN')
            result = self._handoff(ticket_ref)
            if owned_transaction:
                self.ledger.connection.commit()
            return result
        except Exception:
            if owned_transaction:
                self.ledger.connection.rollback()
            raise

    def _handoff(self, ticket_ref: str) -> dict:
        packet, inspection, compatible = self._load(ticket_ref, require_ready=False)
        coverage = self.ledger.plan_coverage(packet['plan_id'])
        indexed_controls = self.ledger.calibration_reviews()
        remote_pages, replays, controls, remote_ids = [], [], [], set()
        for event in self.ledger.snapshot()['events']:
            payload = event['payload']
            if payload.get('continuation_schema') != 1:
                continue
            if payload.get('mode') == 'remote' and payload.get('ticket_ref') == ticket_ref:
                self._remote_event(event['id'])
                remote_ids.add(event['id'])
                remote_pages.append({'event_id': event['id'], 'review_status': event['review_status'],
                    'start': payload['page']['start'], 'stop': payload['page']['stop'],
                    'state': 'REPLAY_REQUIRED', 'certified_negative': False})
            elif payload.get('mode') == 'replay' and payload.get('remote_event_id') in remote_ids:
                replays.append({'event_id': event['id'], 'review_status': event['review_status'], **payload})
            elif payload.get('mode') == 'controls' and payload.get('ticket_ref') == ticket_ref:
                report = loads(self.workspace.get(payload['report_ref']))
                indexed = indexed_controls.get(event['id'])
                qualifying = indexed is not None and self._qualifying_controls(packet, indexed, report)
                controls.append({'event_id': event['id'], 'review_status': event['review_status'],
                                 'internally_indexed': indexed is not None,
                                 'qualifying_local_record': qualifying, 'report': report})
        try:
            self._preparation(ticket_ref)
        except ValueError:
            prepared = False
        else:
            prepared = True
        active_controls = [row['report'] for row in controls if row['review_status'] == 'RECORDED'
                           and row['qualifying_local_record']]
        calibration_state = (active_controls[-1]['status'] if active_controls else
                             'NOT_RUN' if packet['case']['calibrations'] else 'NO_CALIBRATIONS')
        unresolved_controls = [row['event_id'] for row in controls if row['review_status'] == 'RECORDED'
                               and row['qualifying_local_record']
                               and row['report']['status'] not in ('CALIBRATED', 'NO_CALIBRATIONS')]
        unresolved_replay = any(row['review_status'] == 'RECORDED' and row['status'] != 'MATCH'
                                for row in replays)
        evidence_ready = (inspection['ready'] and inspection['bound_sources_ready'] and
                          compatible and prepared and not unresolved_replay and not unresolved_controls
                          and calibration_state in ('CALIBRATED', 'NO_CALIBRATIONS'))
        conclusion = coverage['conclusion'] if evidence_ready else 'INCONCLUSIVE'
        return {'ticket_ref': ticket_ref, 'inspection': inspection,
                'runtime_compatible': compatible, 'local_coverage': coverage,
                'counts': {'generated_ordinals': packet['generated_ordinals'],
                           'unique_candidates': None, 'unique_completed_ordinals': coverage['counts']['attempted'],
                           'attempted_recorded_ordinals': coverage['counts']['attempted'],
                           'completed_terminal_ordinals': coverage['counts']['attempted'],
                           'valid_completed_ordinals': coverage['counts']['valid'],
                           'overlapping_ordinals': coverage['counts']['overlap']},
                'remote_pages': remote_pages, 'local_replays': replays, 'calibrations': controls,
                'calibration_state': calibration_state, 'conclusion': conclusion,
                'unresolved_control_reports': unresolved_controls,
                'completed_negative': evidence_ready and coverage['complete'] and
                                      conclusion == 'NO_TARGET_MATCH_IN_COMPLETED_PLAN',
                'independent_replay': 'NOT_ESTABLISHED',
                'scope': 'Only internally executed Ledger pages contribute coverage. Distinct candidate values are not counted by ordinal coverage. Remote receipts, source labels and hashes are not authentication; same-code replay is not independent reproduction.'}

    def export_packet(self, ticket_ref: str) -> dict:
        """Portable bytes and manifest only; history/coverage is deliberately absent."""
        packet, _, _ = self._load(ticket_ref, require_ready=False)
        handles = [ticket_ref, *('sha256:' + artifact['sha256'] for artifact in packet['case']['artifacts'])]
        artifacts = []
        for handle in dict.fromkeys(handles):
            try:
                data = self.workspace.get(handle)
            except KeyError:
                artifacts.append({'handle': handle, 'status': 'MISSING', 'base64': None})
            else:
                artifacts.append({'handle': handle, 'status': 'AVAILABLE',
                                  'base64': base64.b64encode(data).decode('ascii')})
        result = {'schema': 1, 'ticket_ref': ticket_ref, 'artifacts': artifacts,
                  'history': 'NOT_EXPORTED', 'independent_replay': 'NOT_ESTABLISHED'}
        if len(encoded(result)) > MAX_TRANSFER:
            raise ValueError('portable packet exceeds 2 MB; retain/export workspace separately')
        return result

    def restore_packet(self, portable: dict) -> dict:
        """Restore exact bytes, never import historical execution as fresh coverage."""
        if (type(portable) is not dict or len(encoded(portable)) > MAX_TRANSFER or
                set(portable) != {'schema', 'ticket_ref', 'artifacts', 'history', 'independent_replay'} or
                portable['schema'] != 1 or portable['history'] != 'NOT_EXPORTED' or
                portable['independent_replay'] != 'NOT_ESTABLISHED' or
                type(portable['artifacts']) is not list or not 1 <= len(portable['artifacts']) <= 33):
            raise ValueError('invalid bounded portable packet')
        seen = set()
        for artifact in portable['artifacts']:
            if (type(artifact) is not dict or set(artifact) != {'handle', 'status', 'base64'} or
                    type(artifact['handle']) is not str or
                    artifact['handle'] in seen):
                raise ValueError('invalid or duplicate portable artifact')
            seen.add(artifact['handle'])
            if artifact['status'] == 'MISSING' and artifact['base64'] is None:
                continue
            if artifact['status'] != 'AVAILABLE' or type(artifact['base64']) is not str:
                raise ValueError('invalid portable artifact state')
            raw = base64.b64decode(artifact['base64'], validate=True)
            if 'sha256:' + hashlib.sha256(raw).hexdigest() != artifact['handle']:
                raise ValueError('portable artifact content/hash mismatch')
            self.workspace.put(raw)
        packet, inspection, compatible = self._load(portable['ticket_ref'], require_ready=False)
        self.ledger.append('observation', {'continuation_schema': 1, 'mode': 'prepared',
            'ticket_ref': portable['ticket_ref']})
        return {'ticket_ref': portable['ticket_ref'], 'inspection': inspection,
                'runtime_compatible': compatible, 'history': 'NOT_IMPORTED',
                'generated_ordinals': packet['generated_ordinals']}

    def close(self) -> None:
        self.ledger.close()
        self.workspace.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
