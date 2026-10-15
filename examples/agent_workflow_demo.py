"""Fresh multi-step crypto workflow regression, not an LLM or open-puzzle solve.

An independent stdlib PNG/cipher producer makes the cases. Polya receives the
artifact, two clue-derived key alternatives, the finite grammar, and an exact
commitment; the producer's answer is used only by the final test assertion.
"""
from __future__ import annotations
import base64
import hashlib
import json
import random
import struct
import zlib

ALPHABET = 'ABCDEFGHIKLMNOPQRSTUVWXYZ'


def _spiral(rows, columns):
    # Independent boundary peeling, not Polya's direction/visited-set walk.
    out = []
    top, bottom, left, right = 0, rows - 1, 0, columns - 1
    while top <= bottom and left <= right:
        out.extend(top * columns + c for c in range(left, right + 1)); top += 1
        out.extend(r * columns + right for r in range(top, bottom + 1)); right -= 1
        if top <= bottom:
            out.extend(bottom * columns + c for c in range(right, left - 1, -1)); bottom -= 1
        if left <= right:
            out.extend(r * columns + left for r in range(bottom, top - 1, -1)); left += 1
    return out


def _encrypt(plain, key, period=7):
    numbers = [(ALPHABET.index(c) + ALPHABET.index(key[i % len(key)])) % 25
               for i, c in enumerate(plain)]
    out = ''
    for start in range(0, len(numbers), period):
        block = numbers[start:start + period]
        digits = ''.join(str(n // 5) for n in block) + ''.join(str(n % 5) for n in block)
        out += ''.join(ALPHABET[5 * int(digits[i]) + int(digits[i + 1])]
                       for i in range(0, len(digits), 2))
    return out.encode('ascii')


def _png(width, height, samples):
    def chunk(kind, raw):
        return struct.pack('!I', len(raw)) + kind + raw + struct.pack('!I', zlib.crc32(kind + raw))
    rows = b''.join(b'\0' + bytes(samples[r * width * 3:(r + 1) * width * 3]) for r in range(height))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!2I5B', width, height, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(rows)) + chunk(b'IEND', b''))


def fixture(seed=7):
    rng = random.Random(seed)
    plain = ''.join(rng.choices(ALPHABET, k=16))
    key = ('CODE', 'BLUE')[seed % 2]
    raw = _encrypt(plain, key)
    channel, bit, invert = (0, 2)[seed % 2], (seed // 2) % 2, (seed // 4) % 2
    samples = [rng.randrange(256) for _ in range(8 * 16 * 3)]
    bits = ''.join(f'{b:08b}' for b in raw)
    for digit, location in zip(bits, _spiral(8, 16)):
        i = location * 3 + channel
        samples[i] = (samples[i] & ~(1 << bit)) | ((int(digit) ^ invert) << bit)
    source = base64.b64encode(_png(16, 8, samples)).decode('ascii')
    def step(oid, parent, field, inputs, binding='text'):
        return {'operation_id': oid, 'bindings': {binding: {'node': parent, 'field': field}},
                'inputs': inputs, 'rationale': 'explicit alternative in the public regression grammar'}
    nodes = [
        {'id': 'samples', 'alternatives': [step('artifact.png_bitplane', 'image', 'value',
            {'channel': c, 'bit': b}, 'png_base64') for c in ('R', 'B') for b in (0, 1)]},
        {'id': 'route', 'alternatives': [step('grid.traverse', 'samples', 'text',
            {'rows': 8, 'columns': 16, 'route': route, 'corner': corner})
            for route in ('spiral_cw', 'spiral_ccw') for corner in ('tl', 'tr', 'bl', 'br')]},
        {'id': 'polarity', 'alternatives': [step('bits.invert', 'route', 'text', {'invert': b}) for b in (False, True)]},
        {'id': 'packed', 'alternatives': [step('bits.pack', 'polarity', 'text', {'bit_order': 'msb', 'tail': 'reject'})]},
        {'id': 'text', 'alternatives': [step('bytes.decode_text', 'packed', 'hex', {'codec': 'ascii'}, 'value_hex')]},
        {'id': 'unmixed', 'alternatives': [step('cipher.bifid', 'text', 'text', {'square': ALPHABET, 'period': 7})]},
        {'id': 'plaintext', 'alternatives': [step('cipher.polyalphabetic', 'unmixed', 'text',
            {'key': k, 'alphabet': ALPHABET}) for k in ('CODE', 'BLUE')]},
        {'id': 'encoded', 'alternatives': [step('text.encode', 'plaintext', 'text', {'codec': 'ascii'})]},
    ]
    plan = {'sources': [{'id': 'image', 'kind': 'png', 'value': source, 'source': 'independent synthetic PNG'}],
            'nodes': nodes, 'candidate': {'node': 'encoded', 'field': 'hex'},
            'target': {'kind': 'direct', 'target': {'kind': 'sha256',
                'value': hashlib.sha256(plain.encode('ascii')).hexdigest(), 'source': 'producer commitment'}}}
    return plan, plain.encode('ascii')


def main():
    from polya import run
    rows = []
    for seed in (7, 12, 18):
        plan, expected = fixture(seed)
        preflight = run('mechanism.plan_inspect', {'plan': plan})['result']
        assert preflight['valid']
        page = run('mechanism.plan_scan', {'plan': plan, 'max_trials': 256})['result']
        assert page['complete']
        found = {bytes.fromhex(h['candidate_hex']) for h in page['matches']}
        assert found == {expected}
        rows.append({'seed': seed, 'recipes': page['recipe_count'], 'matches': len(page['matches']),
                     'kernel_calls': page['kernel_calls'], 'cache_hits': page['cache_hits'],
                     'exact_output_checked': True})
    print(json.dumps({'cases': rows, 'scope': 'Independent producer and exact-output regression. '
        'Grammar supplied; not learned mechanism discovery, blinded LLM evaluation or new open-puzzle progress.'}, indent=2))


if __name__ == '__main__':
    main()
