"""Shared output encoding retains independent receipt hashes and exact bounds."""
from dataclasses import replace
import hashlib
import json
from unittest.mock import patch

import pytest

from polya import catalog


@pytest.mark.parametrize('text', ['plain', 'é🙂', 'a' * 999989])
def test_result_receipt_hash_matches_independent_canonical_encoding(text):
    result = {'text': text}
    encoded = json.dumps(result, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                         allow_nan=False).encode('utf8')
    original = catalog.REGISTRY['text.profile']
    synthetic = replace(original, operation_id='test.output', result=None,
                        kernel=lambda **_: dict(result))
    with patch.dict(catalog.REGISTRY, {'test.output': synthetic}):
        envelope = catalog.run('test.output', {'text': 'synthetic'})
        assert envelope['receipt']['result_sha256'] == hashlib.sha256(encoded).hexdigest()
        op, validated, identity, key = catalog.prepare('test.output', {'text': 'synthetic'})
        assert catalog.make_receipt(op, validated, identity, key, result) == envelope['receipt']
    assert len(encoded) <= 1000000


def test_output_one_byte_over_limit_rejects_before_a_receipt():
    original = catalog.REGISTRY['text.profile']
    result = {'text': 'a' * 999990}
    assert len(json.dumps(result, separators=(',', ':')).encode()) == 1000001
    synthetic = replace(original, operation_id='test.output', result=None,
                        kernel=lambda **_: result)
    with patch.dict(catalog.REGISTRY, {'test.output': synthetic}):
        with pytest.raises(ValueError, match='output admission limit'):
            catalog.run('test.output', {'text': 'synthetic'})
