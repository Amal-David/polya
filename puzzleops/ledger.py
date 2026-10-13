"""Explicit local investigation history, separate from execution caches and tools.

Hash chaining detects accidental edits; it is not authentication against someone
who can rewrite the database. Recording evidence never certifies its truth.
"""
from __future__ import annotations
import hashlib
import json
import sqlite3
import time
import uuid
from .catalog import canonical_json
from .jsonio import loads

KINDS = {'observation','hypothesis','experiment','review','retraction'}
ZERO = '0'*64


class Ledger:
    def __init__(self, path: str):
        self.connection = sqlite3.connect(path, timeout=10)
        self.connection.execute('CREATE TABLE IF NOT EXISTS evidence_events (seq INTEGER PRIMARY KEY, id TEXT UNIQUE NOT NULL, body TEXT NOT NULL, previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL)')
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
            self.connection.commit()
            return event_id
        except Exception:
            self.connection.rollback()
            raise

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
