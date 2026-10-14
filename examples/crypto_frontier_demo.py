"""Exercise a missing bridge: raw PNG -> explicit candidate programs -> calibrated lock.

Fresh synthetic instances with withheld channel/bit/route parameters. The search
receives no plaintext, password, or hidden parameters. The grammar is supplied;
this is not learned mechanism discovery or evidence of improved LLM reasoning.
"""
from __future__ import annotations

import json
from pathlib import Path
from polya import run

DATA = Path(__file__).with_name('data')
CASES = Path(__file__).parent / 'cases' / 'gsmg'


def frontier_plan(png_base64: str, lock: dict) -> dict:
    """Declare the supplied grammar; no candidate extraction/search loop lives here."""
    def ref(node, field):
        return {'node': node, 'field': field}

    def step(operation_id, bindings, inputs, rationale):
        return {'operation_id': operation_id, 'bindings': bindings,
                'inputs': inputs, 'rationale': rationale}

    return {
        'sources': [{'id': 'image', 'kind': 'png', 'value': png_base64,
                     'source': 'synthetic raw PNG fixture'}],
        'nodes': [
            {'id': 'plane', 'alternatives': [
                step('artifact.png_bitplane', {'png_base64': ref('image', 'value')},
                     {'channel': channel, 'bit': bit, 'max_pixels': 65536}, 'declared sample plane')
                for channel in ('R', 'G', 'B') for bit in (0, 1)]},
            {'id': 'route', 'alternatives': [
                step('grid.read', {'text': ref('plane', 'text'), 'rows': ref('plane', 'height'),
                                  'columns': ref('plane', 'width')},
                     {'order': order, 'reverse': reverse}, 'declared grid permutation')
                for order in ('row', 'column', 'row_snake', 'column_snake') for reverse in (False, True)]},
            {'id': 'polarity', 'alternatives': [
                step('bits.invert', {'text': ref('route', 'text')}, {'invert': invert}, 'declared bit polarity')
                for invert in (False, True)]},
            {'id': 'packed', 'alternatives': [
                step('bits.pack', {'text': ref('polarity', 'text')},
                     {'bit_order': order, 'tail': 'reject'}, 'whole bytes, no implicit tail loss')
                for order in ('msb', 'lsb')]},
        ],
        'candidate': ref('packed', 'hex'),
        'target': {'kind': 'openssl', 'lock': lock},
    }


def main() -> dict:
    cases = json.loads((DATA/'crypto-hidden-parameters.json').read_text())
    outputs = []
    for case in cases:
        result = run('mechanism.plan_scan', {'plan': frontier_plan(case['png_base64'], case['lock'])})['result']
        assert result['complete'] and result['matches']
        assert len({row['candidate_hex'] for row in result['matches']}) == 1
        outputs.append({'case': case['id'], 'candidate_programs': result['recipe_count'],
            'unique_candidate_bytes': len({row['candidate_sha256'] for row in result['trials']}),
            'matching_programs': [row['choices'] for row in result['matches']],
            'plan_id': result['plan_id'], 'kernel_calls': result['kernel_calls'],
            'complete': result['complete']})
    control = json.loads((CASES/'gsmg-phase2-control.json').read_text())
    result = run('crypto.openssl_scan', {'candidates': [
        {'id': 'published-phase2-answer', 'value_hex': control['candidate_hex'], 'source': control['source']}],
        'locks': [{'id': 'historical-phase2', 'blob_hex': control['blob_hex'], 'digest': 'sha256',
            'password_mode': 'sha256_hex', 'calibration': control,
            'target': {'kind': 'sha256', 'value': control['plaintext_sha256'],
                       'source': 'OpenSSL-reproduced historical plaintext hash'}}]})['result']
    assert result['complete'] and len(result['matches']) == 1
    return {'synthetic_cases': outputs, 'historical_phase2_reproduced': True,
        'scope': 'Three synthetic supplied-grammar parameter recoveries and one public decryption calibration. '
        'No LLM was evaluated. No new GSMG stage or final password was recovered. '
        'The historical scan reuses its calibration computation, not independent evidence.'}


if __name__ == '__main__':
    print(json.dumps(main(), indent=2))
