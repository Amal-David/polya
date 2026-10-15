"""Portable evidence manifests and known-answer replay. Local data only."""
from __future__ import annotations

import hashlib
import json
import time
from typing import Literal
from pydantic import Field
from .cryptic import Spec

DIGEST = r'^[0-9a-f]{64}$'
REPLAY_OPS = frozenset({'bytes.decode', 'bytes.decode_text', 'text.encode', 'text.profile',
    'grid.read', 'grid.traverse', 'text.symbol_map', 'bytes.from_radix',
    'cipher.polyalphabetic', 'cipher.bifid', 'cipher.checkerboard',
    'crypto.openssl_inspect', 'crypto.openssl_decrypt', 'bits.from_symbols', 'bits.pack'})


def encoded(value) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(',', ':'), allow_nan=False).encode()


class Artifact(Spec):
    id: str = Field(pattern=r'^[a-zA-Z][a-zA-Z0-9_-]{0,63}$')
    encoding: Literal['utf8', 'hex']
    sha256: str = Field(pattern=DIGEST)
    source: str = Field(min_length=1, max_length=512)
    content: str | None = Field(default=None, max_length=262144)
    required: bool = True


class Statement(Spec):
    id: str = Field(min_length=1, max_length=64)
    kind: Literal['observation', 'hypothesis']
    text: str = Field(min_length=1, max_length=2000)
    artifact_ids: list[str] = Field(min_length=1, max_length=32)
    retracted: bool = False


class Calibration(Spec):
    id: str = Field(min_length=1, max_length=64)
    operation_id: str = Field(min_length=1, max_length=80)
    inputs: dict = Field(default_factory=dict)
    artifact_bindings: dict[str, str] = Field(default_factory=dict, max_length=8)
    output_field: str = Field(min_length=1, max_length=80)
    expected_value_sha256: str = Field(pattern=DIGEST)
    source: str = Field(min_length=1, max_length=512)


class CasePack(Spec):
    schema_version: int = Field(default=1, ge=1, le=1)
    id: str = Field(min_length=1, max_length=100)
    question: str = Field(min_length=1, max_length=2000)
    artifacts: list[Artifact] = Field(min_length=1, max_length=32)
    statements: list[Statement] = Field(default_factory=list, max_length=64)
    calibrations: list[Calibration] = Field(default_factory=list, max_length=8)
    open_questions: list[str] = Field(default_factory=list, max_length=32)


class InspectInput(Spec):
    case: CasePack


class ReplayInput(InspectInput):
    timeout_ms: int = Field(default=5000, ge=1, le=60000)


def _prepare(case):
    from .catalog import REGISTRY, canonical_operation_id
    p = CasePack.model_validate(case.model_dump() if isinstance(case, CasePack) else case)
    if len(encoded(p.model_dump())) > 900000:
        raise ValueError('case pack exceeds 900000 bytes')
    for items in (p.artifacts, p.statements, p.calibrations):
        if len({x.id for x in items}) != len(items):
            raise ValueError('duplicate artifact, statement or calibration IDs')
    if any(not q or len(q) > 2000 for q in p.open_questions):
        raise ValueError('open questions must contain 1..2000 characters')
    ids = {a.id for a in p.artifacts}
    for s in p.statements:
        if not set(s.artifact_ids) <= ids:
            raise ValueError('statement refers to an unknown artifact')
    for c in p.calibrations:
        c.operation_id = canonical_operation_id(c.operation_id)
        if c.operation_id not in REPLAY_OPS:
            raise ValueError('calibration operation outside the bounded replay allowlist')
        op = REGISTRY[c.operation_id]
        if (set(c.inputs) & c.artifact_bindings.keys() or
                not set(c.artifact_bindings) <= op.request.model_fields.keys() or
                not set(c.artifact_bindings.values()) <= ids or
                c.output_field not in op.result.model_fields):
            raise ValueError('invalid calibration bindings or output field')
    required_by_calibration = {aid for c in p.calibrations for aid in c.artifact_bindings.values()}
    rows = []
    for a in p.artifacts:
        if a.content is None:
            state = 'MISSING_REQUIRED' if a.required or a.id in required_by_calibration else 'MISSING_OPTIONAL'
            actual, size = None, None
        else:
            if a.encoding == 'hex':
                if len(a.content) % 2 or any(ch not in '0123456789abcdefABCDEF' for ch in a.content):
                    raise ValueError('hex artifact content must be exact even-length hexadecimal')
                raw = bytes.fromhex(a.content)
            else:
                raw = a.content.encode('utf-8', errors='strict')
            actual, size = hashlib.sha256(raw).hexdigest(), len(raw)
            state = 'HASH_MATCH' if actual == a.sha256 else 'HASH_MISMATCH'
        rows.append({'id': a.id, 'status': state, 'sha256': a.sha256, 'observed_sha256': actual,
                     'byte_length': size, 'encoding': a.encoding, 'source': a.source})
    return p, rows


def inspect_case(case: dict) -> dict:
    p, rows = _prepare(case)
    blocked = [r['id'] for r in rows if r['status'] in ('MISSING_REQUIRED', 'HASH_MISMATCH')]
    manifest = p.model_dump()
    # Identity binds original bytes and statements, but absence of an optional
    # payload does not change the manifest's hash references.
    for a in manifest['artifacts']:
        a.pop('content')
    return {'case_id': p.id, 'manifest_sha256': hashlib.sha256(encoded(manifest)).hexdigest(),
            'ready': not blocked, 'blocking_artifacts': blocked, 'artifacts': rows,
            'question': p.question, 'statements': [s.model_dump() for s in p.statements],
            'open_questions': p.open_questions, 'calibration_count': len(p.calibrations),
            'scope': 'Hashes check supplied artifact consistency, not source authenticity. Statements remain caller claims; hypotheses and retractions stay explicit. No kernels executed; readiness does not validate interpretations or calibration.'}


def replay(case: dict, timeout_ms: int = 5000) -> dict:
    from .catalog import run
    request = ReplayInput(case=case, timeout_ms=timeout_ms)
    p, _ = _prepare(request.case)
    report = inspect_case(p.model_dump())
    results = []
    if not report['ready']:
        return {'status': 'BLOCKED_EVIDENCE', 'inspection': report, 'calibrations': [],
                'complete': False, 'scope': 'No calibration or investigation was executed.'}
    content = {a.id: a.content for a in p.artifacts}
    deadline = time.monotonic() + timeout_ms / 1000
    for c in p.calibrations:
        if time.monotonic() >= deadline:
            break
        args = dict(c.inputs)
        args.update({field: content[aid] for field, aid in c.artifact_bindings.items()})
        try:
            envelope = run(c.operation_id, args)
            actual = hashlib.sha256(encoded(envelope['result'][c.output_field])).hexdigest()
        except (ValueError, RuntimeError, ImportError) as exc:
            results.append({'id': c.id, 'status': 'EXECUTION_ERROR', 'error_type': type(exc).__name__})
            continue
        if time.monotonic() >= deadline:
            break
        results.append({'id': c.id, 'status': 'REPLAY_MATCH' if actual == c.expected_value_sha256 else 'REPLAY_MISMATCH',
                        'observed_value_sha256': actual, 'source': c.source,
                        'receipt': envelope['receipt']})
    complete = len(results) == len(p.calibrations)
    ok = complete and all(r['status'] == 'REPLAY_MATCH' for r in results)
    return {'status': 'CALIBRATED' if ok and results else 'NO_CALIBRATIONS' if complete and not results else
                     'PARTIAL' if not complete else 'CALIBRATION_FAILED',
            'inspection': report, 'calibrations': results, 'complete': complete,
            'scope': 'Replay of caller-specified historical controls only. Expected values use SHA256 of canonical JSON. A matched control does not validate unknown stages; failed/partial calibration eliminates no puzzle hypothesis. Cooperative deadlines.'}


def example_case() -> dict:
    text = 'LXFOPVEFRNHR'
    return {'id': 'public-calibration', 'question': 'Can this environment replay the known control?',
            'artifacts': [{'id': 'cipher', 'encoding': 'utf8', 'content': text,
                           'sha256': hashlib.sha256(text.encode()).hexdigest(), 'source': 'public Vigenere control'}],
            'calibrations': [{'id': 'known-answer', 'operation_id': 'cipher.polyalphabetic',
                'inputs': {'key': 'LEMON'}, 'artifact_bindings': {'text': 'cipher'}, 'output_field': 'text',
                'expected_value_sha256': hashlib.sha256(encoded('ATTACKATDAWN')).hexdigest(), 'source': 'known plaintext'}]}


def operations(make):
    return [make('casepack.inspect', 'Inspect an evidence-grounded investigation packet',
                 'Verify artifact hashes; keep missing evidence, hypotheses, retractions and questions explicit in a compact handoff.',
                 InspectInput, inspect_case, 'casepack evidence artifact provenance handoff sources missing investigation',
                 'Consistency of caller-supplied evidence, not authenticity or a solve.', '32 artifacts,64 statements,8 controls,900KB total.',
                 example={'case': example_case()}, case_id=str, manifest_sha256=str, ready=bool, blocking_artifacts=list[str], artifacts=list[dict],
                 question=str, statements=list[dict], open_questions=list[str], calibration_count=int, scope=str),
            make('casepack.replay', 'Replay known calibration checkpoints',
                 'Check required evidence first, then execute bounded allowlisted controls; no upstream code or network.',
                 ReplayInput, replay, 'casepack replay calibration known answers validate artifact reproducible',
                 'Only declared known controls tested; no conclusion about unknown answers.', '8 allowlisted calls,shared cooperative 1..60000ms deadline.',
                 cacheable=False, example={'case': example_case()}, status=str, inspection=dict, calibrations=list[dict], complete=bool, scope=str)]
