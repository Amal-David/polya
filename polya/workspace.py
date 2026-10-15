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
