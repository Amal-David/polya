"""Bounded, typed artifact-to-target plans over registered, non-executable kernels.

Plans are ordered DAGs with explicit alternatives and typed references. The
caller supplies the grammar and target; enumeration is not mechanism discovery.
"""
from __future__ import annotations

import base64
import hashlib
from math import prod
import time
from typing import Annotated, Literal

from pydantic import Field

from .crypto_targets import Lock, Target, raw_hex
from .cryptic import Spec
from .mechanisms import _indexes


class Source(Spec):
    id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z][A-Za-z0-9_-]*$")
    kind: Literal['png', 'symbols', 'bits', 'bytes']
    value: str = Field(max_length=524288)
    source: str = Field(min_length=1, max_length=256)


class Reference(Spec):
    node: str = Field(min_length=1, max_length=64)
    field: str = Field(min_length=1, max_length=64)


class Step(Spec):
    operation_id: Literal['artifact.png_bitplane', 'grid.read', 'encoding.symbol_map',
                          'symbols.to_bits', 'bits.invert', 'bits.pack', 'bytes.slice']
    bindings: dict[str, Reference] = Field(min_length=1, max_length=4)
    inputs: dict = Field(default_factory=dict)
    rationale: str = Field(min_length=1, max_length=512)


class Node(Spec):
    id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z][A-Za-z0-9_-]*$")
    alternatives: list[Step] = Field(min_length=1, max_length=64)


class DirectTarget(Spec):
    kind: Literal['direct']
    target: Target


class OpenSSLTarget(Spec):
    kind: Literal['openssl']
    lock: Lock


class Plan(Spec):
    sources: list[Source] = Field(min_length=1, max_length=4)
    nodes: list[Node] = Field(default_factory=list, max_length=8)
    candidate: Reference
    target: Annotated[DirectTarget | OpenSSLTarget, Field(discriminator='kind')]


class ScanInput(Spec):
    plan: Plan
    start: int = Field(default=0, ge=0)
    expected_plan_id: str | None = Field(default=None, pattern=r'^[0-9a-f]{64}$')
    max_trials: int = Field(default=256, ge=1, le=512)
    max_matches: int = Field(default=16, ge=1, le=16)
    max_work: int = Field(default=4000000, ge=1, le=16000000)
    timeout_ms: int = Field(default=5000, ge=1, le=60000)


# Semantic port kinds are stricter than JSON's string type. No arbitrary dotted
# paths, imports, executable expressions, or operations can enter this table.
_PORTS = {
    'artifact.png_bitplane': ({'png_base64': 'png'}, {'text': 'bits', 'width': 'int', 'height': 'int'}),
    'grid.read': ({'text': 'stream', 'rows': 'int', 'columns': 'int'},
                  {'text': 'stream', 'rows': 'int', 'columns': 'int'}),
    'encoding.symbol_map': ({'text': 'symbols'}, {'text': 'symbols'}),
    'symbols.to_bits': ({'text': 'symbols'}, {'text': 'bits'}),
    'bits.invert': ({'text': 'bits'}, {'text': 'bits'}),
    'bits.pack': ({'text': 'bits'}, {'hex': 'bytes'}),
    'bytes.slice': ({'value_hex': 'bytes'}, {'hex': 'bytes'}),
}
_PRIMARY = {'artifact.png_bitplane': 'png_base64', 'grid.read': 'text',
            'encoding.symbol_map': 'text', 'symbols.to_bits': 'text',
            'bits.invert': 'text', 'bits.pack': 'text', 'bytes.slice': 'value_hex'}
_DUMMIES = {'png': 'AA==', 'symbols': '', 'bits': '', 'bytes': '00' * 16384, 'int': 1}


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _source(source: Source) -> dict:
    """Validate representation before enumerating, without running a decoder."""
    if source.kind == 'png':
        try:
            raw = base64.b64decode(source.value, validate=True)
        except ValueError as exc:
            raise ValueError('PNG source requires canonical base64') from exc
        if base64.b64encode(raw).decode('ascii') != source.value:
            raise ValueError('PNG source requires canonical base64')
    elif source.kind == 'bytes':
        raw = raw_hex(source.value)
    else:
        if len(source.value) > 65536:
            raise ValueError('symbol and bit sources are bounded to 65536 codepoints')
        if source.kind == 'bits' and set(source.value) - {'0', '1'}:
            raise ValueError('bit source must contain only 0 and 1')
        raw = source.value.encode('utf-8')
    return {'id': source.id, 'kind': source.kind, 'sha256': _sha(raw),
            'source': source.source, 'length': len(raw) if source.kind in ('png', 'bytes') else len(source.value),
            'unit': 'encoded PNG byte' if source.kind == 'png' else 'byte' if source.kind == 'bytes' else 'codepoint'}


def prepare_plan(plan: dict | Plan) -> tuple[Plan, str, int, list[dict]]:
    """Validate all ports/constants, then bind identity to semantics and runtime."""
    from .catalog import REGISTRY, canonical_json, implementation_fingerprint
    p = Plan.model_validate(plan)
    if len(canonical_json(p.model_dump()).encode()) > 900000:
        raise ValueError('plan exceeds 900000 serialized bytes')
    sources = [_source(s) for s in p.sources]
    types = {}
    for source in p.sources:
        if source.id in types:
            raise ValueError('source and node IDs must be unique')
        types[source.id] = {'value': source.kind}
    sizes = [len(node.alternatives) for node in p.nodes]
    total = prod(sizes)
    if total > 1000000:
        raise ValueError('at most one million declared recipes')
    for node in p.nodes:
        if node.id in types:
            raise ValueError('source and node IDs must be unique')
        shape = None
        for step in node.alternatives:
            operation = REGISTRY[step.operation_id]
            accepted, outputs = _PORTS[step.operation_id]
            if _PRIMARY[step.operation_id] not in step.bindings:
                raise ValueError('the typed stream input must be an explicit reference')
            if set(step.bindings) & step.inputs.keys():
                raise ValueError('a bound input cannot also be a constant')
            if set(step.bindings) - accepted.keys():
                raise ValueError('unknown or non-referenceable input port')
            args = dict(step.inputs)
            resolved = {}
            for name, ref in step.bindings.items():
                kind = types.get(ref.node, {}).get(ref.field)
                if kind is None:
                    raise ValueError('references must name a declared source or earlier node output')
                expected = accepted[name]
                if (expected == 'stream' and kind not in ('symbols', 'bits')) or (expected != 'stream' and expected != kind):
                    raise ValueError('reference kind does not match the input port; use an explicit conversion')
                resolved[name] = kind
                args[name] = _DUMMIES[kind]
            # Validate every alternative's constants/defaults before any kernel.
            operation.request.model_validate(args)
            current = {key: resolved['text'] if kind == 'stream' else kind for key, kind in outputs.items()}
            if shape is not None and current != shape:
                raise ValueError('alternatives for one node must expose identical typed output ports')
            shape = current
        types[node.id] = shape
    if types.get(p.candidate.node, {}).get(p.candidate.field) != 'bytes':
        raise ValueError('candidate must reference exact bytes; conversion must be explicit')
    # Crypto framing and all calibration fields are checked before enumeration.
    if isinstance(p.target, OpenSSLTarget):
        from .crypto import openssl_inspect
        lock = p.target.lock
        for blob in (lock.blob_hex, lock.calibration.blob_hex):
            raw_hex(blob)
            openssl_inspect(blob)
        raw_hex(lock.calibration.candidate_hex, 4096)
        raw_hex(lock.calibration.plaintext_sha256, 32)
    plan_id = _sha(canonical_json({'schema': 1, 'implementation': implementation_fingerprint(),
                                  'plan': p.model_dump(mode='json')}).encode())
    return p, plan_id, total, sources


def _derivation(node: Node, choice: int, step: Step, args: dict, result: dict) -> dict:
    """Compact, loss-explicit source-coordinate maps, not lossy offset samples."""
    from .catalog import canonical_json
    op = step.operation_id
    if op == 'artifact.png_bitplane':
        mapping = {'kind': 'png_sample_bit', **{k: result[k] for k in
                   ('width', 'height', 'channel', 'bit', 'source_sha256', 'samples_sha256', 'coordinates')}}
        loss = {'kind': 'selected_sample_bit', 'channel': args['channel'], 'bit': args['bit'],
                'scope': 'Other channels and sample bits were not selected; original source hash retained.'}
    elif op == 'grid.read':
        mapping = {'kind': 'grid_permutation', **{k: args[k] for k in ('rows', 'columns', 'order', 'reverse')}}
        loss = {'kind': 'none'}
    elif op == 'encoding.symbol_map':
        mapping = {'kind': 'symbol_expansion', 'mapping': args['mapping']}
        loss = {'kind': 'explicit_symbol_mapping', 'dropped_offsets': result['dropped_offsets']}
    elif op == 'symbols.to_bits':
        mapping = {'kind': 'identity_offsets', 'zero': args['zero'], 'one': args['one']}
        loss = {'kind': 'none'}
    elif op == 'bits.invert':
        mapping = {'kind': 'identity_offsets', 'invert': args['invert']}
        loss = {'kind': 'none'}
    elif op == 'bits.pack':
        mapping = {'kind': 'fixed_bit_groups', 'group_width': 8, 'bit_order': args['bit_order']}
        loss = {'kind': 'explicit_tail', 'tail': args['tail'], 'dropped_offsets': result['dropped_offsets'],
                'consumed_bits': result['consumed_bits']}
    else:
        mapping = {'kind': 'byte_slice', 'start': args['start'], 'stop': args['stop']}
        loss = {'kind': 'explicit_slice', 'dropped_ranges': result['dropped_ranges']}
    return {'node': node.id, 'choice': choice, 'operation_id': op,
            'bindings': {k: v.model_dump() for k, v in step.bindings.items()},
            'constants': step.inputs, 'rationale': step.rationale,
            'inputs_sha256': _sha(canonical_json(args).encode()),
            'result_sha256': _sha(canonical_json(result).encode()), 'mapping': mapping, 'loss': loss}


def scan(**kwargs) -> dict:
    from .catalog import REGISTRY, canonical_json
    request = ScanInput.model_validate(kwargs)
    p, plan_id, total, sources = prepare_plan(request.plan)
    if request.start > total or (request.start and request.expected_plan_id is None):
        raise ValueError('resuming requires an in-range start and the previous plan_id')
    if request.expected_plan_id is not None and request.expected_plan_id != plan_id:
        raise ValueError('plan changed: previous coverage cannot be carried over')
    started = time.monotonic()
    cache = {}
    cache_bytes = calls = reused = work = 0
    trials, matches = [], []
    cursor, reason = request.start, 'trial_limit'
    result_bytes = len(canonical_json(sources).encode()) + 10000
    sizes = [len(node.alternatives) for node in p.nodes]

    class Limit(Exception):
        pass

    def timed():
        if (time.monotonic() - started) * 1000 >= request.timeout_ms:
            raise Limit('time_limit')

    def execute(operation_id: str, args: dict) -> dict:
        nonlocal cache_bytes, calls, reused, work
        timed()
        operation = REGISTRY[operation_id]
        args = operation.request.model_validate(args).model_dump(mode='json')
        encoded = canonical_json(args)
        cache_args = {k: v for k, v in args.items() if k != 'timeout_ms'} if operation_id == 'crypto.openssl_scan' else args
        key = (operation_id, canonical_json(cache_args))
        if key in cache:
            reused += 1
            return cache[key]
        amount = max(1, len(encoded.encode()))
        if work + amount > request.max_work:
            raise Limit('work_limit')
        work += amount
        calls += 1
        output = operation.kernel(**args)
        try:
            result = operation.result.model_validate(output).model_dump(mode='json')
        except ValueError as exc:
            raise RuntimeError('operation violated its output contract') from exc
        timed()  # Finishing a kernel after the deadline does not finish a trial.
        size = amount + len(canonical_json(result).encode())
        cacheable = operation_id != 'crypto.openssl_scan' or result['complete']
        if cacheable and len(cache) < 512 and cache_bytes + size <= 8000000:
            cache[key] = result
            cache_bytes += size
        return result

    try:
        while cursor < min(total, request.start + request.max_trials):
            timed()
            choices = _indexes(cursor, sizes)
            values = {s.id: {'value': s.value} for s in p.sources}
            trace, error = [], None
            for node, choice in zip(p.nodes, choices):
                step = node.alternatives[choice]
                args = dict(step.inputs)
                args.update({name: values[ref.node][ref.field] for name, ref in step.bindings.items()})
                try:
                    output = execute(step.operation_id, args)
                    # Use normalized defaults in the mapping, not assumed values.
                    args = REGISTRY[step.operation_id].request.model_validate(args).model_dump(mode='json')
                    trace.append(_derivation(node, choice, step, args, output))
                    values[node.id] = output
                except ValueError as exc:
                    error = {'node': node.id, 'operation_id': step.operation_id, 'message': str(exc)[:500]}
                    break
            candidate, checked, target_trace = None, None, None
            if error is None:
                candidate = values[p.candidate.node][p.candidate.field]
                try:
                    raw = raw_hex(candidate)
                    if isinstance(p.target, DirectTarget):
                        checked = execute('crypto.target_check', {'candidate_hex': candidate, 'target': p.target.target.model_dump()})
                        outcome = checked['outcome']
                        matched = checked['match']
                        target_trace = {'operation_id': 'crypto.target_check', 'result': checked}
                    else:
                        # Stable content-derived ID allows reuse without losing a recipe's
                        # ordinal/choices/coordinate derivation in the outer result.
                        target_args = {'candidates': [{'id': _sha(raw), 'value_hex': candidate,
                                                       'source': 'typed plan candidate bytes'}],
                                       'locks': [p.target.lock.model_dump()],
                                       'timeout_ms': max(1, int(request.timeout_ms - (time.monotonic() - started) * 1000))}
                        checked = execute('crypto.openssl_scan', target_args)
                        if not checked['complete']:
                            raise Limit(checked['termination_reason'])
                        outcome = checked['trials'][0]['outcome']
                        matched = bool(checked['matches'])
                        target_trace = {'operation_id': 'crypto.openssl_scan', 'result': checked}
                except ValueError as exc:
                    error = {'node': 'target', 'operation_id': 'crypto.target_check' if isinstance(p.target, DirectTarget)
                             else 'crypto.openssl_scan', 'message': str(exc)[:500]}
            timed()
            if error:
                outcome, matched = 'INVALID_RECIPE_INPUT', False
            row = {'ordinal': cursor, 'choices': choices, 'outcome': outcome, 'error': error,
                   'candidate_sha256': _sha(bytes.fromhex(candidate)) if candidate is not None and error is None else None}
            hit = ({**row, 'candidate_hex': candidate, 'candidate_ref': p.candidate.model_dump(), 'derivation': trace, 'target_check': target_trace,
                    'evidence_kind': 'EXACT_TARGET_UNDER_DECLARED_PLAN'} if matched else None)
            size = len(canonical_json(row).encode()) + (len(canonical_json(hit).encode()) if hit else 0)
            if result_bytes + size > 900000:
                raise Limit('output_limit')
            result_bytes += size
            trials.append(row)
            if hit is not None:
                matches.append(hit)
            cursor += 1
            if len(matches) >= request.max_matches:
                reason = 'match_limit'
                break
    except Limit as exc:
        reason = str(exc)
    exhausted = cursor == total
    if exhausted:
        reason = 'exhausted'
    invalid = sum(row['outcome'] in ('INVALID_RECIPE_INPUT', 'READING_NOT_APPLICABLE') for row in trials)
    complete = exhausted and request.start == 0
    return {'status': 'COMPLETE' if complete else 'PARTIAL', 'plan_id': plan_id,
            'recipe_count': total, 'start': request.start, 'stop': cursor,
            'next_start': None if exhausted else cursor, 'complete': complete, 'range_exhausted': exhausted,
            'termination_reason': reason, 'trials': trials, 'matches': matches, 'sources': sources,
            'coverage': {'start': request.start, 'stop': cursor, 'total': total, 'completed': len(trials),
                         'invalid': invalid, 'valid': len(trials) - invalid,
                         'unvisited_ranges': ([[0, request.start]] if request.start else []) + ([[cursor, total]] if cursor < total else [])},
            'conclusion': 'TARGET_MATCH' if matches else 'NO_TARGET_MATCH_IN_COMPLETED_PLAN' if complete and not invalid else 'INCONCLUSIVE',
            'kernel_calls': calls, 'cache_hits': reused, 'work_units': work,
            'scope': 'Only the caller-declared typed recipe product and exact target were tested. '
                     'Enumeration includes explicit invalid inputs, which never establish a negative target result. '
                     'Incomplete trials are retried at the unchanged cursor. A resumed suffix is not a complete search. '
                     'Plan IDs bind source content, choices, targets and implementation/runtime, excluding page budgets. '
                     'Source labels are caller claims; compact coordinate maps are exact derivations, not authenticated evidence. '
                     'Shared kernels/calibration are not independent reproduction. Time is cooperative; work counts validated input JSON bytes on cache misses.'}


def operations(make):
    return [make('mechanism.plan_scan', 'Execute typed artifact-to-target plans',
                 'Compose bounded PNG, symbol, bit and byte references with explicit alternatives, losses and exact targets.',
                 ScanInput, scan, 'typed artifact png symbols bits bytes candidate target plan resume provenance investigation',
                 'Exact target checks under a supplied finite grammar; interruption and invalid inputs never imply a negative puzzle result.',
                 '4 sources,8 nodes,64 alternatives/node,1M recipes,512 trials,16 matches; 65536 bit/symbol units,16384 candidate bytes; time/work/cache/output bounds.',
                 cacheable=False, status=str, plan_id=str, recipe_count=int, start=int, stop=int,
                 next_start=int | None, complete=bool, range_exhausted=bool, termination_reason=str,
                 trials=list[dict], matches=list[dict], sources=list[dict], coverage=dict, conclusion=str,
                 kernel_calls=int, cache_hits=int, work_units=int, scope=str)]
