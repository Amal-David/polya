"""Independent review oracle: 512 exact grid/inversion/packing recipes."""
import hashlib
import itertools
import random

from puzzleops.plans import scan


def test_512_grid_invert_pack_recipes():
    rng = random.Random(917)
    orders = ['row', 'column', 'row_snake', 'column_snake']

    def indexes(order):
        if order == 'row':
            return list(range(16))
        if order == 'column':
            return [8*r+c for c in range(8) for r in range(2)]
        if order == 'row_snake':
            return list(range(8)) + list(range(15, 7, -1))
        return [8*r+c for c in range(8) for r in ([0, 1] if c % 2 == 0 else [1, 0])]

    def step(op, node, field='text', **inputs):
        return {'operation_id': op, 'bindings': {'text': {'node': node, 'field': field}},
                'inputs': inputs, 'rationale': 'independent review'}

    for _ in range(32):
        bits = ''.join(rng.choice('01') for _ in range(16))
        expected = []
        for order, invert, bit_order in itertools.product(orders, [False, True], ['msb', 'lsb']):
            read = ''.join(bits[i] for i in indexes(order))
            if invert:
                read = ''.join('1' if char == '0' else '0' for char in read)
            expected.append(bytes(sum((read[i+j] == '1') << (7-j if bit_order == 'msb' else j)
                                      for j in range(8)) for i in range(0, 16, 8)))
        plan = {
            'sources': [{'id': 's', 'kind': 'bits', 'value': bits, 'source': 'random seed 917'}],
            'nodes': [
                {'id': 'g', 'alternatives': [step('grid.read', 's', 'value', rows=2, columns=8, order=x)
                                             for x in orders]},
                {'id': 'i', 'alternatives': [step('bits.invert', 'g', invert=x) for x in [False, True]]},
                {'id': 'p', 'alternatives': [step('bits.pack', 'i', bit_order=x) for x in ['msb', 'lsb']]},
            ],
            'candidate': {'node': 'p', 'field': 'hex'},
            'target': {'kind': 'direct', 'target': {'kind': 'sha256',
                        'value': hashlib.sha256(expected[0]).hexdigest(), 'source': 'independent fixture'}},
        }
        result = scan(plan=plan)
        assert result['complete'] and len(result['trials']) == 16
        assert [row['candidate_sha256'] for row in result['trials']] == [hashlib.sha256(x).hexdigest() for x in expected]
        for hit in result['matches']:
            assert hit['candidate_hex'] == expected[hit['ordinal']].hex()
            assert hit['derivation'][0]['mapping']['order'] == orders[hit['choices'][0]]
            assert hit['derivation'][1]['mapping']['invert'] == [False, True][hit['choices'][1]]
            assert hit['derivation'][2]['mapping']['bit_order'] == ['msb', 'lsb'][hit['choices'][2]]

