"""Whole-output equality partitions under explicit byte/digest conventions.

This is a conditional consumer of supplied bytes, never a candidate generator.
Pattern symbols are Unicode codepoints, with no normalization or ignored units.
"""
from __future__ import annotations

import hashlib
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .crypto_targets import Strict, raw_hex

Position = Annotated[int, Field(ge=0, lt=8192)]
Positions = Annotated[list[Position], Field(max_length=8192)]
Length = Annotated[int, Field(ge=0, le=8192)]

SCOPE = (
    'Every position of the complete declared output is checked under one shared '
    'bijection between observed units and pattern codepoints. A match establishes '
    'only this equality relation under the supplied digest/representation, not '
    'the intended producer, a fixed substitution alphabet, or a puzzle solution. '
    'Source labels are caller assertions; no normalization or truncation occurs.'
)


class EqualityPattern(Strict):
    pattern: str = Field(min_length=1, max_length=8192)
    source: str = Field(min_length=1, max_length=256)
    digest: Literal['none', 'sha256', 'sha512']
    representation: Literal['bytes', 'hex_lower', 'hex_upper']

    @model_validator(mode='after')
    def validate_pattern(self):
        # Surrogate codepoints are not Unicode scalar values; JSON can contain
        # them, but they cannot be retained as canonical UTF-8 source evidence.
        self.pattern.encode('utf-8')
        self.source.encode('utf-8')
        return self


class CheckInput(Strict):
    candidate_hex: str = Field(max_length=8192)
    target: EqualityPattern


class BijectionEntry(Strict):
    pattern_symbol: str = Field(min_length=1, max_length=1)
    output_symbol: Annotated[int, Field(ge=0, le=255)] | Annotated[str, Field(min_length=1, max_length=1)]
    first_position: Position


def _partition(units: str | bytes) -> list[int]:
    """Canonical block IDs, ordered by first appearance; O(number of units)."""
    blocks = {}
    return [blocks.setdefault(unit, len(blocks)) for unit in units]


def check(candidate_hex: str, target: dict) -> dict:
    p = CheckInput(candidate_hex=candidate_hex, target=target)
    raw = raw_hex(p.candidate_hex, 4096)
    spec = p.target
    output = raw if spec.digest == 'none' else hashlib.new(spec.digest, raw).digest()
    units = output if spec.representation == 'bytes' else output.hex()
    if spec.representation == 'hex_upper':
        units = units.upper()
    expected, observed = _partition(spec.pattern), _partition(units)
    common = min(len(expected), len(observed))
    mismatches = [i for i in range(common) if expected[i] != observed[i]]
    missing = list(range(common, len(expected)))
    extra = list(range(common, len(observed)))
    matched = not (mismatches or missing or extra)
    mapping = []
    if matched:
        seen = set()
        for index, symbol in enumerate(spec.pattern):
            if symbol not in seen:
                seen.add(symbol)
                mapping.append({'pattern_symbol': symbol, 'output_symbol': units[index],
                                'first_position': index})
    return {
        'match': matched, 'outcome': 'TARGET_MATCH' if matched else 'NO_TARGET_MATCH',
        'candidate_sha256': hashlib.sha256(raw).hexdigest(),
        'target': spec.model_dump(), 'output_hex': output.hex(),
        'output_unit': 'byte' if spec.representation == 'bytes' else 'hex codepoint',
        'expected_length': len(expected), 'observed_length': len(observed),
        'expected_partition': expected, 'observed_partition': observed,
        'mismatch_positions': mismatches, 'missing_positions': missing,
        'extra_positions': extra, 'bijection': mapping, 'scope': SCOPE,
    }


def operations(make):
    return [make(
        'pattern.equality_check', 'Check a whole-output equality partition',
        'Compare every output position under one shared bijection after an explicit digest and byte/hex representation.',
        CheckInput, check, 'equality partition pattern bijection digest sha256 sha512 bytes hex full output target',
        SCOPE, '4096 candidate bytes; 8192 pattern codepoints; fixed digest allowlist; linear work and complete evidence.',
        match=bool, outcome=Literal['TARGET_MATCH', 'NO_TARGET_MATCH'],
        candidate_sha256=str, target=EqualityPattern, output_hex=str,
        output_unit=Literal['byte', 'hex codepoint'], expected_length=Length,
        observed_length=Length, expected_partition=Positions, observed_partition=Positions,
        mismatch_positions=Positions, missing_positions=Positions, extra_positions=Positions,
        bijection=Annotated[list[BijectionEntry], Field(max_length=8192)], scope=str,
    )]
