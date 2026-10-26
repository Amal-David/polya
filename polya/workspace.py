"""Opt-in local artifact handles and ledger-backed restart packets.

Only a Python host chooses the directory. No filesystem paths, uploads or database
writes are exposed through puzzle.run. A workspace is not an access-control sandbox.
"""
from __future__ import annotations
import base64
from copy import deepcopy
import hashlib
from pathlib import Path
import re
import sqlite3

from .casepacks import MAX_STORED_ARTIFACT as MAX_ARTIFACT, encoded, inspect_case
from .jsonio import loads

HANDLE = re.compile(r'^sha256:([a-f0-9]{64})$')
MAX_TOTAL = 32_000_000


class Workspace:
    def __init__(self, directory: str | Path):
        self.root = Path(directory)
        self.root.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.root / 'artifacts.sqlite', timeout=5)
        self.connection.execute('CREATE TABLE IF NOT EXISTS artifacts (sha TEXT PRIMARY KEY, body BLOB NOT NULL)')
        self.connection.commit()

    def put(self, data: bytes) -> str:
        if type(data) is not bytes or len(data) > MAX_ARTIFACT:
            raise ValueError('artifact must be exact bytes of at most one megabyte')
        sha = hashlib.sha256(data).hexdigest()
        try:
            self.connection.execute('BEGIN IMMEDIATE')
            found = self.connection.execute('SELECT length(body) FROM artifacts WHERE sha=?', (sha,)).fetchone()
            if found is None:
                count, size = self.connection.execute('SELECT count(*),coalesce(sum(length(body)),0) FROM artifacts').fetchone()
                if count >= 512 or size + len(data) > MAX_TOTAL:
                    raise ValueError('workspace capacity exceeded: 512 artifacts / 32 MB')
                self.connection.execute('INSERT INTO artifacts VALUES (?,?)', (sha, data))
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise
        # Do not silently accept a coherently named but corrupted preexisting blob.
        self.get('sha256:' + sha)
        return 'sha256:' + sha

    def get(self, handle: str) -> bytes:
        if type(handle) is not str or not HANDLE.fullmatch(handle):
            raise ValueError('expected an exact sha256 handle, never a filesystem path')
        sha = handle[7:]
        row = self.connection.execute('SELECT length(body) FROM artifacts WHERE sha=?', (sha,)).fetchone()
        if row is None:
            raise KeyError(handle)
        if row[0] > MAX_ARTIFACT:
            raise ValueError('stored artifact exceeds admission bound')
        row = self.connection.execute('SELECT substr(body,1,?) FROM artifacts WHERE sha=?', (MAX_ARTIFACT + 1, sha)).fetchone()
        data = row[0] if row is not None else None
        if type(data) is not bytes or len(data) > MAX_ARTIFACT or hashlib.sha256(data).hexdigest() != sha:
            raise ValueError('artifact content/hash mismatch')
        return data

    def hydrate_plan(self, plan: dict) -> dict:
        """Resolve explicit source artifact_ref values; retain source conventions."""
        if type(plan) is not dict or len(encoded(plan)) > MAX_ARTIFACT:
            raise ValueError('plan must be a bounded JSON object')
        resolved = deepcopy(plan)
        for source in resolved.get('sources', []):
            if 'artifact_ref' not in source:
                continue
            if 'value' in source:
                raise ValueError('a source cannot have both artifact_ref and value')
            data = self.get(source.pop('artifact_ref'))
            if source.get('kind') == 'png':
                source['value'] = base64.b64encode(data).decode('ascii')
            elif source.get('kind') == 'bytes':
                source['value'] = data.hex()
            elif source.get('kind') in ('symbols', 'bits'):
                source['value'] = data.decode('utf-8', errors='strict')
            else:
                raise ValueError('declare a supported source kind before hydration')
        from .plans import prepare_plan
        return prepare_plan(resolved)[0].model_dump(mode='json')

    def save_plan(self, plan: dict) -> str:
        return self.put(encoded(self.hydrate_plan(plan)))

    def run_plan(self, plan: dict, **limits) -> dict:
        if 'plan' in limits:
            raise ValueError('limits cannot override the plan')
        from .ledger import Ledger
        with Ledger(self.root / 'history.sqlite') as ledger:
            return ledger.run('mechanism.plan_scan', {'plan': self.hydrate_plan(plan), **limits})

    def run_recorded(self, operation_id: str, inputs: dict, *,
                     dependencies: list[str] | None = None) -> dict:
        """Execute uncached and retain the exact canonical request and envelope.

        Like Ledger.run, execution uses an owned canonical JSON snapshot, whose
        object keys are sorted. Both stored blobs are bounded to one megabyte;
        the response bound includes the receipt. Returned partial/negative
        results retain their scope. Raised or interrupted calls publish no event.
        """
        return self._run_recorded(operation_id, inputs, dependencies=dependencies)

    def _run_recorded(self, operation_id: str, inputs: dict, *,
                      dependencies: list[str] | None = None,
                      replay_of: dict | None = None) -> dict:
        from .ledger import Ledger
        references = {}

        def before_execute(op_id: str, normalized: dict, identity: dict) -> None:
            request = encoded({'operation_id': op_id, 'inputs': normalized})
            if len(request) > MAX_ARTIFACT:
                raise ValueError('recorded request exceeds the one megabyte artifact bound')
            if replay_of is not None:
                previous = replay_of['envelope']['receipt']
                if (op_id != replay_of['operation_id'] or
                        encoded(normalized) != encoded(replay_of['inputs']) or
                        identity['operation_version'] != previous['operation_version'] or
                        identity['implementation'] != previous['implementation_fingerprint'] or
                        identity['runtime_mode'] != previous['runtime_observations']['after']):
                    raise ValueError('recorded execution is incompatible with the current request/version/runtime')
            sha = hashlib.sha256(request).hexdigest()
            present = self.connection.execute('SELECT 1 FROM artifacts WHERE sha=?', (sha,)).fetchone()
            if present is not None:
                self.get('sha256:' + sha)
            count, size = self.connection.execute(
                'SELECT count(*),coalesce(sum(length(body)),0) FROM artifacts').fetchone()
            # Reject an already exhausted store before running a potentially
            # expensive operation. Final result size and concurrent writes are
            # checked by put; at least one response slot must be available.
            new_request = int(present is None)
            if count + new_request + 1 > 512 or size + new_request * len(request) >= MAX_TOTAL:
                raise ValueError('workspace capacity exceeded for a recorded request and response')

        def record_artifacts(op_id: str, normalized: dict, envelope: dict) -> dict:
            if set(envelope) != {'operation_id', 'result', 'receipt'}:
                raise ValueError('recorded execution must return the complete uncached catalog envelope')
            request = encoded({'operation_id': op_id, 'inputs': normalized})
            response = encoded(envelope)
            if len(response) > MAX_ARTIFACT:
                raise ValueError('recorded response including its receipt exceeds the one megabyte artifact bound')
            references.update(schema=1, request_ref=self.put(request),
                              response_ref=self.put(response),
                              replay_of=None if replay_of is None else replay_of['ledger_event_id'])
            return dict(references)

        with Ledger(self.root / 'history.sqlite') as ledger:
            envelope = ledger._run(operation_id, inputs, dependencies=dependencies,
                                   before_execute=before_execute,
                                   record_artifacts=record_artifacts)
        return {**envelope, 'request_ref': references['request_ref'],
                'response_ref': references['response_ref']}

    def load_recorded(self, event_id: str) -> dict:
        """Load exact archived bytes and current review state, without executing.

        Historical records remain inspectable after upgrades. Content hashes and
        the internal execution index detect inconsistency, not a database owner
        rewriting history. Caller-appended receipt claims cannot be loaded here.
        """
        from .ledger import Ledger
        with Ledger(self.root / 'history.sqlite') as ledger:
            event = ledger._execution_event(event_id)
        payload = event['payload']
        references = payload.get('recorded_run')
        if (type(references) is not dict or
                set(references) != {'schema', 'request_ref', 'response_ref', 'replay_of'} or
                type(references['schema']) is not int or references['schema'] != 1):
            raise ValueError('execution has no supported durable request/response record')
        replay_of = references['replay_of']
        if replay_of is not None and (type(replay_of) is not str or replay_of not in event['dependencies']):
            raise ValueError('recorded replay dependency is inconsistent')
        request = loads(self.get(references['request_ref']))
        envelope = loads(self.get(references['response_ref']))
        if (type(request) is not dict or set(request) != {'operation_id', 'inputs'} or
                type(request['inputs']) is not dict or type(envelope) is not dict or
                set(envelope) != {'operation_id', 'receipt', 'result'} or
                type(envelope['result']) is not dict or
                request['operation_id'] != payload['operation_id'] or
                envelope['operation_id'] != payload['operation_id'] or
                encoded(envelope['receipt']) != encoded(payload['receipt'])):
            raise ValueError('recorded request/response does not match its execution')
        receipt = payload['receipt']
        if (hashlib.sha256(encoded(request['inputs'])).hexdigest() != receipt['inputs_sha256'] or
                hashlib.sha256(encoded(envelope['result'])).hexdigest() != receipt['result_sha256']):
            raise ValueError('recorded request/result receipt hashes do not match')
        return {'ledger_event_id': event_id, 'operation_id': request['operation_id'],
                'inputs': request['inputs'], 'envelope': envelope,
                'request_ref': references['request_ref'], 'response_ref': references['response_ref'],
                'dependencies': event['dependencies'], 'review_status': event['review_status'],
                'replay_of': replay_of, 'independently_reproduced': False,
                'scope': 'Exact locally recorded request and response; source labels and stored history are not authenticated. Retractions request review rather than refuting the encoded result.'}

    def replay_recorded(self, event_id: str) -> dict:
        """Rerun the saved request uncached under a compatible version/runtime.

        A fresh indexed execution depends on the original event, carrying its
        invalidation chain. Comparison uses canonical result hashes, including
        elapsed statistics; disagreement need not be a semantic disagreement.
        Same-implementation reruns never establish independent reproduction.
        """
        previous = self.load_recorded(event_id)
        if previous['review_status'] != 'RECORDED':
            raise ValueError('retracted or review-required executions cannot be replayed')
        envelope = self._run_recorded(previous['operation_id'], previous['inputs'],
                                      dependencies=[event_id], replay_of=previous)
        matches = (envelope['receipt']['result_sha256'] ==
                   previous['envelope']['receipt']['result_sha256'])
        return {**envelope, 'replay': {
            'original_event_id': event_id, 'status': 'MATCH' if matches else 'MISMATCH',
            'original_result_sha256': previous['envelope']['receipt']['result_sha256'],
            'result_sha256': envelope['receipt']['result_sha256'],
            'independently_reproduced': False,
            'scope': 'Fresh uncached execution; comparison covers exact canonical result content, including timing/statistics. A mismatch is not by itself a semantic failure, and a match is not independent reproduction or proof of puzzle interpretation.'}}

    def handoff(self, case: dict, plan_ids: list[str]) -> dict:
        """Compact caller claims plus actual recorded coverage; no fabricated summaries."""
        if type(plan_ids) is not list or len(plan_ids) > 32 or len(set(plan_ids)) != len(plan_ids):
            raise ValueError('at most 32 distinct plan IDs')
        from .ledger import Ledger
        report = inspect_case(case, artifact_loader=self.get)
        with Ledger(self.root / 'history.sqlite') as ledger:
            coverage = [ledger.plan_coverage(pid) for pid in plan_ids]
        result = {'case': report, 'plans': coverage,
                  'scope': 'Compact case claims and internally executed ledger coverage. Artifact payloads remain local; caller statement text is included and this method calls no model. Retractions and gaps remain visible. Recheck plan identity after upgrades.'}
        if len(encoded(result)) > 1_000_000:
            raise ValueError('handoff exceeds 1 MB; request fewer plans')
        return result

    def close(self):
        self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
