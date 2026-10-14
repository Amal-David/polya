"""Independent verification of a specialist cipher-engine proposal.

Only candidate data is accepted; no external engine or untrusted code is run.
"""
from __future__ import annotations
import hashlib
from typing import Literal
from pydantic import Field
from .cryptic import Spec

class Proposal(Spec):
    engine: str = Field(min_length=1, max_length=100)
    revision: str = Field(min_length=1, max_length=128)
    artifact_sha256: str = Field(
        pattern=r'^[0-9a-f]{64}$',
        description='SHA-256 of the exact ciphertext encoded as UTF-8, without normalization or an added byte-order mark; not the original artifact bytes.',
    )
    ciphertext: str = Field(min_length=1, max_length=16384)
    plaintext: str = Field(min_length=1, max_length=16384)
    key: str = Field(min_length=1, max_length=1024)
    alphabet: str = Field(default='ABCDEFGHIJKLMNOPQRSTUVWXYZ', min_length=2, max_length=256)
    variant: Literal['vigenere','beaufort','variant_beaufort'] = 'vigenere'
    expected_plaintext_sha256: str | None = Field(
        default=None, pattern=r'^[0-9a-f]{64}$',
        description='Optional SHA-256 commitment to the exact plaintext encoded as UTF-8, without normalization or an added byte-order mark.',
    )
    checkpoint_source: str | None = Field(
        default=None, min_length=1, max_length=512,
        description='Caller-supplied, unauthenticated source label for the plaintext commitment; required together with expected_plaintext_sha256.',
    )

def verify_proposal(**kwargs) -> dict:
    p = Proposal.model_validate(kwargs)
    if (p.expected_plaintext_sha256 is None) != (p.checkpoint_source is None):
        raise ValueError('a plaintext commitment and its source must be supplied together')
    digest = hashlib.sha256(p.ciphertext.encode('utf8')).hexdigest()
    if digest != p.artifact_sha256:
        raise ValueError('proposal concerns a different ciphertext artifact')
    if len(set(p.alphabet)) != len(p.alphabet):
        raise ValueError('alphabet must have distinct codepoints')
    if (set(p.ciphertext) | set(p.plaintext) | set(p.key)) - set(p.alphabet):
        raise ValueError('proposal uses characters outside declared alphabet; no implicit normalization')
    size = len(p.alphabet)
    replay = []
    for i, letter in enumerate(p.plaintext):
        plain = p.alphabet.index(letter)
        key = p.alphabet.index(p.key[i % len(p.key)])
        if p.variant == 'vigenere':
            encoded = (plain + key) % size
        elif p.variant == 'beaufort':
            encoded = (key - plain) % size
        else:
            encoded = (plain - key) % size
        replay.append(p.alphabet[encoded])
    consistent = ''.join(replay) == p.ciphertext
    observed = hashlib.sha256(p.plaintext.encode('utf8')).hexdigest()
    committed = None if p.expected_plaintext_sha256 is None else observed == p.expected_plaintext_sha256
    return {'replay_consistent':consistent, 'commitment_match':committed,
            'status':'REJECTED' if not consistent or committed is False else 'CHECKPOINT_MATCH' if committed else 'MECHANISM_CONSISTENT_ONLY',
            'plaintext_sha256':observed,
            'expected_plaintext_sha256':p.expected_plaintext_sha256,
            'checkpoint_source':p.checkpoint_source, 'digest_encoding':'utf-8',
            'engine':p.engine, 'revision':p.revision,
            'scope':'Replay checks a supplied proposal, not that this engine ran or its search is complete. A valid key/plaintext pair need not be the intended solution. The checkpoint source label is caller-supplied and unauthenticated. All digests cover the exact text encoded as UTF-8, without normalization or an added byte-order mark, not original artifact bytes.'}

def operations(make):
    return [make('specialist.verify_proposal','Verify a specialist-engine candidate',
        'Check artifact identity and independently re-encrypt periodic-cipher proposals.',
        Proposal,verify_proposal,'specialist decipher colossus verify engine proposal candidate cipher',
        'Independent re-encryption under supplied conventions, without calling the external solver. All SHA-256 digests cover exact ciphertext/plaintext encoded as UTF-8, without normalization or an added byte-order mark, not original artifact bytes. Checkpoint source labels are caller-supplied and unauthenticated.',
        'Periodic Vigenere/Beaufort only; 16384 ciphertext characters, 1024 key characters.',
        replay_consistent=bool,commitment_match=bool|None,
        status=Literal['REJECTED','CHECKPOINT_MATCH','MECHANISM_CONSISTENT_ONLY'],
        plaintext_sha256=str,expected_plaintext_sha256=str|None,checkpoint_source=str|None,
        digest_encoding=Literal['utf-8'],engine=str,revision=str,scope=str)]
