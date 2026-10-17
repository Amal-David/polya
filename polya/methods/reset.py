"""Append-only controller archive, with fresh proposer packets and stable duplicate IDs.

Read-only files plus content hashes detect accidental corruption. This is NOT an
OS security boundary against a same-user process; deploy controller storage outside
proposer permissions when an actual model/tool runner is connected.
"""
from __future__ import annotations
import hashlib
import json
import math
import os
import tempfile
from pathlib import Path


def canonical(value: object) -> bytes:
    # Reject Python-only values instead of silently coercing tuples or dict keys.
    stack = [(value, 0)]
    seen = 0
    characters = 0
    while stack:
        item, depth = stack.pop()
        seen += 1
        if seen > 100_000 or depth > 64:
            raise ValueError('JSON exceeds node/depth limit')
        if type(item) is dict:
            if any(type(key) is not str for key in item):
                raise ValueError('JSON object keys must be strings')
            if seen + len(stack) + len(item) > 100_000:
                raise ValueError('JSON exceeds node limit')
            characters += sum(len(key) for key in item)
            stack.extend((child, depth + 1) for child in item.values())
        elif type(item) is list:
            if seen + len(stack) + len(item) > 100_000:
                raise ValueError('JSON exceeds node limit')
            stack.extend((child, depth + 1) for child in item)
        elif type(item) not in (str, int, float, bool, type(None)):
            raise ValueError('value must be JSON data')
        if type(item) is str:
            characters += len(item)
        if characters > 2_000_000:
            raise ValueError('JSON exceeds 2 MB')
    raw = json.dumps(value, sort_keys=True, separators=(',', ':'),
                     ensure_ascii=False, allow_nan=False).encode('utf-8')
    if len(raw) > 2_000_000:
        raise ValueError('JSON exceeds 2 MB')
    return raw


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


class Archive:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)

    def _put(self, kind: str, value: dict) -> tuple[str, bool]:
        # Snapshot once: caller-owned nested objects may change after serialization.
        raw = canonical(value)
        if len(raw) > 2_000_000:
            raise ValueError('archive record exceeds 2 MB')
        h = hashlib.sha256(raw).hexdigest()
        directory = self.path / kind
        directory.mkdir(exist_ok=True)
        dest = directory / (h + '.json')
        # Publish a fully written inode atomically; concurrent duplicates never see
        # a partially written destination. Local filesystem must support hard links.
        fd, staging = tempfile.mkstemp(prefix='.staging-', dir=directory)
        try:
            with os.fdopen(fd, 'wb') as handle:
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
            # Windows read-only attributes also prevent unlinking hard links.
            # Immutability is an API contract, not a permissions boundary.
            if os.name != 'nt':
                os.chmod(staging, 0o444)
            try:
                os.link(staging, dest)
                created = True
            except FileExistsError:
                if dest.read_bytes() != raw:
                    raise ValueError('archive corruption')
                created = False
        finally:
            os.unlink(staging)
        return h, created

    def record_attempt(self, experiment: dict) -> tuple[str, bool]:
        """Identity excludes narrative; caller includes exact inputs/method/budget/version."""
        required = {'method', 'inputs', 'budget', 'version'}
        if not isinstance(experiment, dict) or set(experiment) != required:
            raise ValueError('experiment requires method, inputs, budget, version')
        if not isinstance(experiment['method'], str) or not experiment['method']:
            raise ValueError('method required')
        h, created = self._put('attempts', experiment)
        return h, not created

    def record_verified(self, claim: str, receipt: dict, checker: str) -> str:
        """Controller attestation only: does not itself establish factual truth."""
        if (not isinstance(claim, str) or not claim.strip() or
                not isinstance(checker, str) or not checker.strip() or
                not isinstance(receipt, dict) or not receipt):
            raise ValueError('claim, nonempty receipt and independent checker required')
        return self._put('evidence', {'claim': claim, 'receipt': receipt, 'checker': checker})[0]

    def fresh_packet(self, problem: str, *, evidence_ids: list[str], remaining_budget: dict,
                     scope: str = 'Educational toy puzzles only; no external target actions.') -> dict:
        """Only explicitly selected verified evidence; no prior proposals or chain of thought."""
        if (not isinstance(problem, str) or not problem.strip() or
                not isinstance(evidence_ids, list) or len(evidence_ids) > 32):
            raise ValueError('problem required; at most 32 evidence items')
        if not isinstance(scope, str) or not scope.strip():
            raise ValueError('scope required')
        allowed = {'input_tokens', 'output_tokens', 'tool_calls', 'wall_seconds', 'resets'}
        if not isinstance(remaining_budget, dict) or set(remaining_budget) - allowed:
            raise ValueError('unknown budget fields')
        for k, v in remaining_budget.items():
            if (type(v) not in (int, float) or
                    (type(v) is float and not math.isfinite(v)) or v < 0):
                raise ValueError('finite nonnegative remaining budget required')
            if k != 'wall_seconds' and type(v) is not int:
                raise ValueError('integer counters required')
        evidence = []
        for h in evidence_ids:
            if not isinstance(h, str) or len(h) != 64 or any(c not in '0123456789abcdef' for c in h):
                raise ValueError('invalid evidence id')
            from .library import read_json
            item = read_json(self.path / 'evidence' / (h + '.json'))
            if digest(item) != h:
                raise ValueError('evidence hash mismatch')
            evidence.append({'id': h, **item})
        return {'problem': problem, 'scope': scope, 'verified_evidence': evidence,
                'remaining_budget': remaining_budget.copy(),
                'duplicate_check': 'controller checks canonical experiment hash before execution'}
