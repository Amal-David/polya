"""Bounded unknown-key periodic-cipher baseline, scored against supplied text.

No word-list download, live verifier, modern cipher cracking or hidden language
model. Every output is a heuristic candidate with exact re-encryption checked.
"""
from __future__ import annotations
from collections import Counter
from math import log
import time
from typing import Literal
from pydantic import Field
from .cryptic import Spec


class Input(Spec):
    text: str = Field(min_length=8, max_length=8192)
    alphabet: str = Field(default='ABCDEFGHIJKLMNOPQRSTUVWXYZ', min_length=2, max_length=64)
    reference_text: str = Field(min_length=8, max_length=32768)
    reference_source: str = Field(min_length=1, max_length=512)
    periods: list[int] = Field(min_length=1, max_length=16)
    variant: Literal['vigenere', 'beaufort', 'variant_beaufort'] = 'vigenere'
    shifts_per_column: int = Field(default=3, ge=1, le=8)
    beam_width: int = Field(default=32, ge=1, le=128)
    top_k: int = Field(default=5, ge=1, le=16)
    max_work: int = Field(default=2000000, ge=1, le=8000000)
    timeout_ms: int = Field(default=5000, ge=1, le=60000)


def _primitive(key: str) -> str:
    for size in range(1, len(key) + 1):
        if len(key) % size == 0 and key == key[:size] * (len(key) // size):
            return key[:size]
    raise AssertionError('unreachable')


def search(**kwargs) -> dict:
    p = Input.model_validate(kwargs)
    alphabet = p.alphabet
    size = len(alphabet)
    if len(set(alphabet)) != size or (set(p.text) | set(p.reference_text)) - set(alphabet):
        raise ValueError('alphabet must be unique and cover exact ciphertext/reference; normalize explicitly outside this operation')
    if (len(set(p.periods)) != len(p.periods) or
            any(type(x) is not int or not 1 <= x <= min(32, len(p.text) // 2) for x in p.periods)):
        raise ValueError('periods must be distinct strict integers in 1..min(32,text_length//2)')
    ids = {c: i for i, c in enumerate(alphabet)}
    observed = [ids[c] for c in p.text]
    reference = Counter(p.reference_text)
    log_probs = [log((reference[c] + 1) / (len(p.reference_text) + size)) for c in alphabet]
    work, evaluated, completed = 0, 0, []
    found: dict[str, dict] = {}
    deadline = time.monotonic() + p.timeout_ms / 1000
    reason = 'declared_search_exhausted'

    class Budget(Exception):
        pass

    def charge(amount):
        nonlocal work
        if time.monotonic() >= deadline:
            raise Budget('time_limit')
        if work + amount > p.max_work:
            raise Budget('work_limit')
        work += amount

    def plain_symbol(c, k):
        return ((c - k) if p.variant == 'vigenere' else
                (c + k) if p.variant == 'variant_beaufort' else (k - c)) % size

    try:
        for period in p.periods:
            charge(len(observed))
            columns = []
            for pos in range(period):
                hist = Counter(observed[pos::period])
                charge(size * len(hist))
                scores = [(sum(count * log_probs[plain_symbol(c, k)] for c, count in hist.items()), k)
                          for k in range(size)]
                columns.append(sorted(scores, key=lambda x: (-x[0], x[1]))[:p.shifts_per_column])
            beam = [(0.0, ())]
            for options in columns:
                charge(len(beam) * len(options))
                beam = sorted([(score + part, key + (k,)) for score, key in beam for part, k in options],
                              key=lambda x: (-x[0], x[1]))[:p.beam_width]
            for score, key in beam:
                charge(len(observed))
                plaintext_ids = [plain_symbol(c, key[i % period]) for i, c in enumerate(observed)]
                # Separate full forward arithmetic checks every supplied ciphertext symbol.
                def forward(x, k):
                    return ((x + k) if p.variant == 'vigenere' else
                            (x - k) if p.variant == 'variant_beaufort' else (k - x)) % size
                if any(forward(x, key[i % period]) != observed[i] for i, x in enumerate(plaintext_ids)):
                    raise RuntimeError('candidate failed full re-encryption')
                evaluated += 1
                key_text = _primitive(''.join(alphabet[k] for k in key))
                row = {'key': key_text, 'plaintext': ''.join(alphabet[x] for x in plaintext_ids),
                       'negative_log_likelihood': -score,
                       'ranking_cost': -score + len(key_text) * log(size),
                       'origin_periods': [period], 'reencryption_matches': True,
                       'evidence_kind': 'HEURISTIC_CANDIDATE_ONLY'}
                if key_text in found:
                    if period not in found[key_text]['origin_periods']:
                        found[key_text]['origin_periods'].append(period)
                else:
                    found[key_text] = row
                # Only retain the strongest bounded portfolio in memory; this is
                # deliberately not exhaustive key enumeration or a reusable proof.
                if len(found) > p.top_k * 4:
                    keep = sorted(found.values(), key=lambda r: (r['ranking_cost'], r['key']))[:p.top_k * 2]
                    found = {r['key']: r for r in keep}
            completed.append(period)
    except Budget as exc:
        reason = str(exc)
    candidates = sorted(found.values(), key=lambda r: (r['ranking_cost'], r['key']))[:p.top_k]
    return {'candidates': candidates, 'completed_periods': completed, 'candidate_keys_evaluated': evaluated,
            'work_units': work, 'termination_reason': reason, 'complete_declared_search': len(completed) == len(p.periods),
            'full_keyspace_exhausted': False, 'reference_source': p.reference_source,
            'scope': 'Repeating-key classical-cipher hypotheses only. Add-one unigram likelihood from caller reference text plus key-length*log(alphabet_size) ranking penalty. Beam pruning is heuristic. Re-encryption checks implementation, not plaintext meaning. Uniform, short, adversarial or different-language inputs may mislead. No exact target, modern cryptographic shortcut or puzzle solution is inferred.'}


def operations(make):
    return [make('cipher.periodic_search', 'Propose unknown periodic-cipher keys',
                 'Score all column shifts against caller-supplied reference text, then retain a bounded beam and re-encrypt every emitted candidate.',
                 Input, search, 'unknown key vigenere beaufort periodic classical cryptanalysis statistical search',
                 'Heuristic key/plaintext proposals only; exact re-encryption does not certify intended meaning.',
                 '8192 ciphertext symbols,16 periods<=32,64-symbol alphabet,128 beam,16 results; work/time bounds.',
                 cacheable=False, candidates=list[dict], completed_periods=list[int], candidate_keys_evaluated=int,
                 work_units=int, termination_reason=str, complete_declared_search=bool, full_keyspace_exhausted=bool,
                 reference_source=str, scope=str)]
